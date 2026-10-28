"""Демо-стенд (D-10): заготовленные кадры — настоящий инференс.

Кадры отобраны заранее, чтобы показ был предсказуемым и выразительным, но
предсказания считаются моделью в момент запуска и проходят тот же путь, что и
боевые кадры: ``ingest_frame`` → Snapshot + Detection → Alert → статус
площадки. После прогона UI показывает живые данные: алерты с фото и рамками,
статусы на карте, историю на странице площадки.

Кадры берутся из каталога (по умолчанию ``ml/demo_frames``), имена как у
сборщика: ``cam{key}_YYYY-MM-DD_HHMMSS.jpg``. Камеры демо-организации
создаются по ключам кадров и раскладываются по её площадкам. Повторный запуск
не дублирует данные: уже принятые кадры (та же камера, то же время съёмки)
пропускаются.

Запуск:  cd backend && venv/bin/python -m app.demo_stand [--dir DIR] [--org NAME]
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.db.database import SessionLocal
from app.db.models import Alert, Camera, Organization, Site, Snapshot
from app.ingest import ingest_frame
from app.scheduler import parse_frame_name

logger = logging.getLogger(__name__)

DEFAULT_FRAMES_DIR = BASE_DIR.parent / "ml" / "demo_frames"
DEFAULT_ORG = "ТКО Мониторинг — демо"


def ensure_cameras(db: Session, org: Organization, keys: list[str]) -> dict[str, Camera]:
    """Камера на каждый ключ кадра, раскиданные по площадкам организации."""
    sites = (
        db.query(Site)
        .filter(Site.organization_id == org.id)
        .order_by(Site.id)
        .all()
    )
    if not sites:
        raise SystemExit(f"у организации «{org.name}» нет площадок — сначала python -m app.seed")

    by_key: dict[str, Camera] = {}
    for i, key in enumerate(sorted(keys)):
        cam = (
            db.query(Camera)
            .join(Site, Camera.site_id == Site.id)
            .filter(Camera.external_key == key, Site.organization_id == org.id)
            .first()
        )
        if cam is None:
            cam = Camera(
                site_id=sites[i % len(sites)].id,
                name=f"Камера №{key} (демо)",
                rtsp_url=f"rtsp://demo/cam{key}",
                external_key=key,
                is_active=True,
            )
            db.add(cam)
            db.flush()
            logger.info("создана камера external_key=%s на площадке «%s»", key, sites[i % len(sites)].name)
        by_key[key] = cam
    db.commit()
    return by_key


def run_demo(db: Session, frames_dir: Path, org_name: str) -> dict[str, int]:
    org = db.query(Organization).filter(Organization.name == org_name).first()
    if org is None:
        raise SystemExit(f"организация «{org_name}» не найдена — сначала python -m app.seed")

    frames: list[tuple[str, object, Path]] = []
    for path in sorted(frames_dir.iterdir() if frames_dir.is_dir() else []):
        parsed = parse_frame_name(path.name)
        if parsed:
            frames.append((parsed[0], parsed[1], path))
    if not frames:
        raise SystemExit(
            f"в {frames_dir} нет кадров вида cam{{key}}_YYYY-MM-DD_HHMMSS.jpg"
        )

    cameras = ensure_cameras(db, org, sorted({key for key, _, _ in frames}))
    _resolve_seed_alerts(db, org)

    counts = {"ingested": 0, "skipped": 0}
    # Хронологический порядок: статус площадки в итоге отражает последний кадр.
    for key, taken_at, path in sorted(frames, key=lambda f: f[1]):
        camera = cameras[key]
        stored_at = taken_at.replace(tzinfo=None)
        exists = (
            db.query(Snapshot)
            .filter(Snapshot.camera_id == camera.id, Snapshot.taken_at == stored_at)
            .first()
        )
        if exists:
            counts["skipped"] += 1
            continue
        result = ingest_frame(db, camera, path, taken_at)
        counts["ingested"] += 1
        verdict = result.verdict
        logger.info(
            "%s: %d детекций (переполнение=%s, навал=%s), алертов %d",
            path.name, len(verdict.detections),
            verdict.has_overflow, verdict.has_contamination, len(result.created_alerts),
        )
    return counts


def _resolve_seed_alerts(db: Session, org: Organization) -> None:
    """Гасит открытые сид-алерты (они без снапшота) на площадках организации.

    Иначе дедупликация в ingest_frame честно подавит новые алерты — а смысл
    демо как раз в алертах с фотографией и рамками.
    """
    import datetime as dt

    stale = (
        db.query(Alert)
        .join(Site, Alert.site_id == Site.id)
        .filter(
            Site.organization_id == org.id,
            Alert.status != "resolved",
            Alert.snapshot_id.is_(None),
        )
        .all()
    )
    for alert in stale:
        alert.status = "resolved"
        alert.resolution_reason = "resolved_externally"
        alert.resolved_at = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    if stale:
        db.commit()
        logger.info("погашено %d сид-алертов без фото", len(stale))


def main() -> int:
    parser = argparse.ArgumentParser(description="Демо-стенд: прогон заготовленных кадров")
    parser.add_argument("--dir", default=str(DEFAULT_FRAMES_DIR), help="каталог с кадрами")
    parser.add_argument("--org", default=DEFAULT_ORG, help="имя демо-организации")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    with SessionLocal() as db:
        counts = run_demo(db, Path(args.dir), args.org)
    logger.info("готово: %(ingested)d кадров прогнано, %(skipped)d уже было", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
