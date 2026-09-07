"""Перевзвод живого показа: «забыть» кадры из ml/live_demo.

После репетиции живого момента (кадр → алерт → Telegram) система считает кадр
принятым и второй раз его не возьмёт (дедуп по камере+времени съёмки), а
открытый алерт подавит новые уведомления. Этот скрипт возвращает исходное
состояние: удаляет снапшоты этих кадров (с детекциями), их алерты и
пересчитывает статус площадки — живой показ можно повторять сколько угодно.

Трогает ТОЛЬКО кадры из указанного каталога, остальные демо-данные целы.

Запуск:  python -m app.demo_rearm [--dir ml/live_demo]
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.db.database import SessionLocal
from app.db.models import Alert, Camera, Site, Snapshot
from app.scheduler import parse_frame_name

logger = logging.getLogger(__name__)

DEFAULT_DIR = BASE_DIR.parent / "ml" / "live_demo"


def rearm(db: Session, frames_dir: Path) -> int:
    removed = 0
    touched_sites: set[int] = set()

    for path in sorted(frames_dir.iterdir() if frames_dir.is_dir() else []):
        parsed = parse_frame_name(path.name)
        if not parsed:
            continue
        key, taken_at = parsed
        stored_at = taken_at.replace(tzinfo=None)
        cameras = db.query(Camera).filter(Camera.external_key == key).all()
        for camera in cameras:
            snap = (
                db.query(Snapshot)
                .filter(Snapshot.camera_id == camera.id, Snapshot.taken_at == stored_at)
                .first()
            )
            if snap is None:
                continue
            alerts = db.query(Alert).filter(Alert.snapshot_id == snap.id).all()
            for alert in alerts:
                db.delete(alert)
            db.delete(snap)  # детекции уходят каскадом
            touched_sites.add(camera.site_id)
            removed += 1
            logger.info("%s: снапшот %d и %d алерт(а) удалены", path.name, snap.id, len(alerts))

    # Удаления должны попасть в БД ДО пересчёта статусов: сессия работает с
    # autoflush=False, и без flush() запрос ниже видел бы удалённые алерты.
    db.flush()

    # Статус площадки — по оставшимся нерешённым алертам.
    for site_id in touched_sites:
        site = db.query(Site).filter(Site.id == site_id).first()
        levels = {
            a.level
            for a in db.query(Alert).filter(Alert.site_id == site_id, Alert.status != "resolved")
        }
        site.status = (
            "overflow" if "overflow" in levels
            else "contamination" if "contamination" in levels
            else "clean"
        )
        logger.info("площадка «%s»: статус → %s", site.name, site.status)

    db.commit()
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Перевзвод кадров живого показа")
    parser.add_argument("--dir", default=str(DEFAULT_DIR), help="каталог живых кадров")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    with SessionLocal() as db:
        removed = rearm(db, Path(args.dir))
    logger.info("перевзведено кадров: %d", removed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
