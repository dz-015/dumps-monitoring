"""Съём кадров с платформы Watcher в каталог планировщика.

Заменяет прежнюю цепочку «сборщик → S3 → синк»: камеры переехали на платформу,
и наш сервер снимает кадр у неё напрямую. Дальше ничего не меняется — кадр
кладётся в INGEST_DIR по тому же контракту имён, что и раньше, а подбирает его
тот же app/scheduler.py.

Устройство:
- обходим активные камеры, у которых заполнено ``watcher_stream``;
- кадр пишем во временный файл и переименовываем: планировщик никогда не
  увидит недописанный JPEG;
- камера без сигнала просто пропускается — на платформе сейчас живы не все.

Запуск:  python -m app.watcher_sync --once            # один проход (cron)
         python -m app.watcher_sync --interval 3600   # вечный цикл (compose)
Без настроек платформы процесс мирно спит — как боты без токена.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app import watcher
from app.config import settings
from app.db.database import SessionLocal
from app.db.models import Camera

logger = logging.getLogger(__name__)


def frame_name(camera_key: str, taken_at: dt.datetime) -> str:
    """Имя кадра по контракту планировщика: cam7_2026-09-21_084734.jpg."""
    return f"cam{camera_key}_{taken_at:%Y-%m-%d_%H%M%S}.jpg"


def watched_cameras(db: Session) -> list[Camera]:
    """Активные камеры, привязанные к потоку на платформе."""
    return (
        db.query(Camera)
        .filter(
            Camera.is_active.is_(True),
            Camera.watcher_stream.isnot(None),
            Camera.external_key.isnot(None),
        )
        .order_by(Camera.external_key)
        .all()
    )


def _write_frame(ingest_dir: Path, name: str, data: bytes) -> None:
    """Атомарная укладка: пишем в .tmp и переименовываем."""
    ingest_dir.mkdir(parents=True, exist_ok=True)
    tmp = ingest_dir / f"{name}.tmp"
    tmp.write_bytes(data)
    tmp.rename(ingest_dir / name)


def sync_once(db: Session, ingest_dir: Path | str) -> int:
    """Один проход по всем камерам. Возвращает число снятых кадров."""
    ingest_dir = Path(ingest_dir)
    cameras = watched_cameras(db)
    if not cameras:
        logger.info("Watcher-синк: нет камер с привязанным потоком")
        return 0

    written = 0
    for camera in cameras:
        # Планировщик и БД хранят время без часового пояса, поэтому срезаем его.
        taken_at = dt.datetime.now(dt.UTC).replace(tzinfo=None, microsecond=0)
        try:
            jpeg = watcher.grab_jpeg(camera.watcher_stream)
        except Exception:
            # Сбой одной камеры не должен рушить обход остальных.
            logger.exception("Watcher-синк: ошибка съёма камеры %s", camera.watcher_stream)
            continue
        if not jpeg:
            continue
        name = frame_name(camera.external_key, taken_at)
        _write_frame(ingest_dir, name, jpeg)
        written += 1
        logger.info("Watcher-синк: %s (%d КБ)", name, len(jpeg) // 1024)

    logger.info("Watcher-синк: снято %d кадров из %d камер", written, len(cameras))
    return written


def run_once() -> int:
    with SessionLocal() as db:
        return sync_once(db, settings.INGEST_DIR)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Съём кадров с платформы Watcher")
    parser.add_argument("--once", action="store_true", help="один проход и выход")
    parser.add_argument("--interval", type=int, default=settings.WATCHER_INTERVAL_SECONDS,
                        help="пауза между проходами, секунд")
    args = parser.parse_args()

    if not watcher.enabled():
        logger.warning("Настройки платформы не заданы — синк выключен, сплю.")
        if args.once:
            return 0
        while True:
            time.sleep(3600)

    if args.once:
        run_once()
        return 0

    logger.info("Watcher-синк запущен, интервал %d с", args.interval)
    while True:
        try:
            run_once()
        except Exception:
            logger.exception("Watcher-синк: проход упал целиком")
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
