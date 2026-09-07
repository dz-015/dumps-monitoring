"""Синк кадров сборщика: S3-бакет → INGEST_DIR (последняя перемычка контура).

Сборщик (collector/) кладёт кадры в S3-совместимое хранилище по ключам
``cameras/{id}/YYYY/MM/DD/HHMMSS.jpg`` (время съёмки — UTC). Здесь мы раз в
интервал листим бакет по префиксу каждой активной камеры (``external_key``
совпадает с id камеры в БД сборщика), скачиваем новое и кладём в INGEST_DIR
под именем ``cam{key}_YYYY-MM-DD_HHMMSS.jpg`` — дальше кадры подбирает
app/scheduler.py.

Устройство:
- маркер (последний синхронизированный ключ на камеру) — JSON в
  ``INGEST_DIR/.sync/state.json``. На первом запуске маркер ставится на самый
  свежий объект БЕЗ выкачивания истории — в бакете десятки тысяч кадров;
- скачивание идёт во временный файл в ``.sync/`` с атомарным rename в
  INGEST_DIR: параллельный scheduler никогда не видит недокачанный кадр;
- кадр, уже лежащий в INGEST_DIR / processed/ / failed/, повторно не
  скачивается (маркер всё равно двигается).

Запуск:  python -m app.s3_sync --once           # один проход (cron)
         python -m app.s3_sync --interval 600   # вечный цикл (compose)
Без S3-кредов в окружении процесс мирно спит — как боты без токена.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import SessionLocal
from app.db.models import Camera

logger = logging.getLogger(__name__)

# cameras/3/2026/08/03/134500.jpg → cam3, 2026-08-03, 134500, jpg
_S3_KEY = re.compile(
    r"^cameras/(?P<cam>[^/]+)/(?P<y>\d{4})/(?P<m>\d{2})/(?P<d>\d{2})/(?P<hms>\d{6})\.(?P<ext>jpe?g|png)$",
    re.IGNORECASE,
)

_STATE_DIR = ".sync"
_STATE_FILE = "state.json"


def enabled() -> bool:
    return bool(settings.S3_ENDPOINT_URL and settings.S3_SNAPSHOTS_BUCKET)


def key_to_frame_name(key: str) -> str | None:
    """Ключ бакета → имя кадра по контракту планировщика, иначе None."""
    match = _S3_KEY.match(key)
    if not match:
        return None
    return (
        f"cam{match['cam']}_{match['y']}-{match['m']}-{match['d']}"
        f"_{match['hms']}.{match['ext'].lower()}"
    )


def load_state(ingest_dir: Path) -> dict[str, str]:
    path = Path(ingest_dir) / _STATE_DIR / _STATE_FILE
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def save_state(ingest_dir: Path, state: dict[str, str]) -> None:
    state_dir = Path(ingest_dir) / _STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    tmp = state_dir / f"{_STATE_FILE}.tmp"
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True))
    tmp.rename(state_dir / _STATE_FILE)


def active_keys(db: Session) -> list[str]:
    """Ключи сборщика, за которыми следим: активные камеры с external_key."""
    rows = (
        db.query(Camera.external_key)
        .filter(Camera.is_active.is_(True), Camera.external_key.isnot(None))
        .distinct()
        .all()
    )
    return sorted({key for (key,) in rows if key})


def _list_keys(s3, bucket: str, prefix: str, start_after: str):
    """Все ключи префикса после start_after, в порядке возрастания."""
    token = None
    while True:
        kwargs = {"Bucket": bucket, "Prefix": prefix, "StartAfter": start_after}
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kwargs)
        for obj in resp.get("Contents", []):
            yield obj["Key"]
        if not resp.get("IsTruncated"):
            return
        token = resp.get("NextContinuationToken")


def _already_handled(ingest_dir: Path, frame_name: str) -> bool:
    return any(
        (ingest_dir / sub / frame_name).exists() if sub else (ingest_dir / frame_name).exists()
        for sub in ("", "processed", "failed")
    )


def sync_prefix(
    s3, bucket: str, cam_key: str, marker: str | None, ingest_dir: Path
) -> tuple[str | None, int]:
    """Один префикс камеры: докачать новое после маркера.

    Возвращает (новый маркер, сколько кадров скачано). При marker=None история
    не выкачивается — маркер встаёт на самый свежий существующий ключ.
    """
    ingest_dir = Path(ingest_dir)
    prefix = f"cameras/{cam_key}/"

    if marker is None:
        last = None
        for key in _list_keys(s3, bucket, prefix, ""):
            last = key
        if last:
            logger.info("cam %s: первый запуск, маркер → %s (история пропущена)", cam_key, last)
        return last, 0

    downloaded = 0
    tmp_dir = ingest_dir / _STATE_DIR
    for key in _list_keys(s3, bucket, prefix, marker):
        marker = key
        frame_name = key_to_frame_name(key)
        if frame_name is None:
            logger.warning("cam %s: ключ %s не по схеме — пропущен", cam_key, key)
            continue
        if _already_handled(ingest_dir, frame_name):
            continue
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp = tmp_dir / f"{frame_name}.part"
        s3.download_file(bucket, key, str(tmp))
        tmp.rename(ingest_dir / frame_name)
        downloaded += 1
    return marker, downloaded


def sync_once(db: Session, s3, bucket: str, ingest_dir: Path) -> dict[str, int]:
    """Один проход по всем активным камерам. Возвращает счётчики для лога."""
    ingest_dir = Path(ingest_dir)
    state = load_state(ingest_dir)
    counts = {"downloaded": 0, "prefixes": 0}
    for cam_key in active_keys(db):
        marker, downloaded = sync_prefix(s3, bucket, cam_key, state.get(cam_key), ingest_dir)
        if marker is not None:
            state[cam_key] = marker
        counts["downloaded"] += downloaded
        counts["prefixes"] += 1
    save_state(ingest_dir, state)
    return counts


def make_client():
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Синк кадров S3 → ingest")
    parser.add_argument("--dir", default=settings.INGEST_DIR, help="каталог планировщика")
    parser.add_argument("--once", action="store_true", help="один проход и выход")
    parser.add_argument("--interval", type=int, default=600, help="пауза между проходами, сек")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not enabled():
        logger.warning("S3-креды не заданы — синк выключен, сплю.")
        while True:
            time.sleep(3600)

    ingest_dir = Path(args.dir)
    ingest_dir.mkdir(parents=True, exist_ok=True)
    s3 = make_client()

    while True:
        try:
            with SessionLocal() as db:
                counts = sync_once(db, s3, settings.S3_SNAPSHOTS_BUCKET, ingest_dir)
            logger.info(
                "проход завершён: %(downloaded)d кадров с %(prefixes)d камер", counts
            )
        except Exception:
            logger.exception("проход синка упал, продолжаю по расписанию")
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
