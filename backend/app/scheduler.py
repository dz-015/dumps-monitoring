"""Часовой контур: приём кадров сборщика из каталога.

Контракт с доставкой кадров — каталог INGEST_DIR с файлами, названными как у
сборщика: ``cam{key}_YYYY-MM-DD_HHMMSS.jpg`` (время съёмки — UTC). Как кадры
попадают в каталог — забота синка (rsync/S3-клиент), не планировщика: так
контур работает одинаково локально, в docker-томе и на прод-хосте.

Каждый проход:
- берёт все кадры из каталога (не рекурсивно),
- находит ВСЕ активные камеры по ``external_key`` из имени файла — одна
  физическая камера может быть заведена в нескольких организациях (демо-стенд
  и реальный заказчик смотрят один поток), кадр получает каждая,
- прогоняет боевой ``ingest_frame`` (инференс → Snapshot → Alert); инференс
  выполняется один раз на кадр — вердикт зависит только от ключа камеры,
- перекладывает кадр в ``processed/`` либо ``failed/`` — каталог никогда не
  разрастается и ни один кадр не обрабатывается дважды.

Запуск:  python -m app.scheduler --once            # один проход (cron)
         python -m app.scheduler --interval 3600   # вечный цикл
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import re
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import SessionLocal
from app.db.models import Camera
from app.ingest import ingest_frame

logger = logging.getLogger(__name__)

FRAME_NAME = re.compile(r"^cam(?P<key>\w+)_(?P<date>\d{4}-\d{2}-\d{2})_(?P<time>\d{6})\.(jpe?g|png)$", re.IGNORECASE)


def parse_frame_name(name: str) -> tuple[str, dt.datetime] | None:
    """cam2_2026-05-08_084734.jpg → ("2", 2026-05-08 08:47:34 UTC), иначе None."""
    match = FRAME_NAME.match(name)
    if not match:
        return None
    taken_at = dt.datetime.strptime(
        f"{match['date']}_{match['time']}", "%Y-%m-%d_%H%M%S"
    ).replace(tzinfo=dt.UTC)
    return match["key"], taken_at


def find_cameras(db: Session, key: str) -> list[Camera]:
    return (
        db.query(Camera)
        .filter(Camera.external_key == key, Camera.is_active.is_(True))
        .order_by(Camera.id)
        .all()
    )


class _MemoPipeline:
    """Кэш вердикта на один кадр: у камер веера общий ключ, значит общие ROI —
    гонять инференс по разу на организацию было бы чистой тратой CPU."""

    def __init__(self, inner):
        self._inner = inner
        self._verdict = None

    def run(self, image, camera_key=None, taken_at=None):
        if self._verdict is None:
            self._verdict = self._inner.run(image, camera_key=camera_key, taken_at=taken_at)
        return self._verdict


def process_dir(db: Session, ingest_dir: Path, pipeline=None) -> dict[str, int]:
    """Один проход по каталогу. Возвращает счётчики для лога/теста."""
    if pipeline is None:
        from app.ml.pipeline import get_pipeline

        pipeline = get_pipeline()

    counts = {"processed": 0, "failed": 0}
    processed_dir = ingest_dir / "processed"
    failed_dir = ingest_dir / "failed"

    for frame in sorted(p for p in ingest_dir.iterdir() if p.is_file()):
        parsed = parse_frame_name(frame.name)
        if parsed is None:
            logger.warning("%s: имя не по схеме cam{key}_YYYY-MM-DD_HHMMSS — в failed/", frame.name)
            _move(frame, failed_dir)
            counts["failed"] += 1
            continue
        key, taken_at = parsed

        cameras = find_cameras(db, key)
        if not cameras:
            logger.warning("%s: нет активной камеры с external_key=%s — в failed/", frame.name, key)
            _move(frame, failed_dir)
            counts["failed"] += 1
            continue

        # Кадр уходит в processed/, если его принял хоть кто-то: повторная
        # обработка задублировала бы снимки успевшим камерам.
        memo = _MemoPipeline(pipeline)
        ok = 0
        for camera in cameras:
            try:
                ingest_frame(db, camera, frame, taken_at, pipeline=memo)
                ok += 1
            except Exception:
                logger.exception("%s: ошибка обработки камерой id=%d", frame.name, camera.id)
                db.rollback()
        if ok:
            _move(frame, processed_dir)
            counts["processed"] += 1
        else:
            _move(frame, failed_dir)
            counts["failed"] += 1

    return counts


def _move(frame: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    frame.rename(dest_dir / frame.name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Часовой контур приёма кадров")
    parser.add_argument("--dir", default=settings.INGEST_DIR, help="каталог с кадрами")
    parser.add_argument("--once", action="store_true", help="один проход и выход")
    parser.add_argument("--interval", type=int, default=3600, help="пауза между проходами, сек")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ingest_dir = Path(args.dir)
    ingest_dir.mkdir(parents=True, exist_ok=True)

    while True:
        with SessionLocal() as db:
            counts = process_dir(db, ingest_dir)
        logger.info("проход завершён: %(processed)d обработано, %(failed)d в failed", counts)
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
