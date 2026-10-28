"""Приём кадра: инференс → Snapshot + Detection → Alert → статус площадки.

Единственная точка входа кадра в систему. Планировщик (часовой контур) и
демо-стенд (D-10) вызывают одну и ту же функцию, поэтому демонстрация честно
показывает боевой код, а не отдельную витрину.

Правила алертов:
- переполнение и навал — независимые уровни, по каждому свой алерт;
- пока по площадке висит нерешённый алерт уровня, новый НЕ создаётся —
  оператору не нужен второй сигнал о той же куче каждый час;
- после resolve следующий кадр с проблемой создаёт свежий алерт.
"""

from __future__ import annotations

import datetime as dt
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Alert, Camera, Detection, Site, Snapshot
from app.ml.pipeline import Verdict

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestResult:
    snapshot: Snapshot
    created_alerts: list[Alert]
    verdict: Verdict


def ingest_frame(
    db: Session,
    camera: Camera,
    frame_path: Path,
    taken_at: dt.datetime,
    pipeline=None,
) -> IngestResult:
    """Прогоняет кадр через пайплайн и записывает результат в БД.

    `taken_at` — время СЪЁМКИ кадра (не приёма): от него зависит выбор
    периода ROI для камер, где баки переставляли.
    """
    if pipeline is None:
        from app.ml.pipeline import get_pipeline
        pipeline = get_pipeline()

    image = Image.open(frame_path)
    image.load()
    verdict = pipeline.run(image, camera_key=camera.external_key, taken_at=taken_at)

    # Кадр копируется в uploads/ — фронтенд отдаёт его как /uploads/<image_path>,
    # а исходный каталог планировщик может чистить независимо.
    dest_dir = Path(settings.UPLOAD_DIR) / "snapshots"
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = frame_path.suffix.lower() or ".jpg"
    dest_name = f"cam{camera.id}_{taken_at:%Y%m%d_%H%M%S}{suffix}"
    shutil.copyfile(frame_path, dest_dir / dest_name)

    # В БД время хранится наивным UTC (как и server_default=func.now()).
    stored_at = taken_at.astimezone(dt.UTC).replace(tzinfo=None) \
        if taken_at.tzinfo else taken_at

    snapshot = Snapshot(
        site_id=camera.site_id,
        camera_id=camera.id,
        image_path=f"snapshots/{dest_name}",
        taken_at=stored_at,
    )
    db.add(snapshot)
    db.flush()

    for d in verdict.detections:
        db.add(
            Detection(
                snapshot_id=snapshot.id,
                class_name=d.class_name,
                confidence=round(d.confidence, 4),
                x=d.x, y=d.y, w=d.w, h=d.h,
            )
        )

    created_alerts = []
    levels = []
    if verdict.has_overflow:
        levels.append("overflow")
    if verdict.has_contamination:
        levels.append("contamination")
    for level in levels:
        if _has_open_alert(db, camera.site_id, level):
            continue
        alert = Alert(
            site_id=camera.site_id,
            snapshot_id=snapshot.id,
            level=level,
            status="new",
        )
        db.add(alert)
        created_alerts.append(alert)

    site = db.query(Site).filter(Site.id == camera.site_id).first()
    if site is not None:
        # Переполнение важнее навала (тот же приоритет, что в
        # sites._derive_active_status).
        site.status = (
            "overflow" if verdict.has_overflow
            else "contamination" if verdict.has_contamination
            else "clean"
        )
    camera.last_checked = dt.datetime.now(dt.UTC).replace(tzinfo=None)

    db.commit()
    db.refresh(snapshot)

    # Уведомления — только ПОСЛЕ коммита и best-effort: упавший Telegram не
    # должен откатить принятый кадр.
    if created_alerts:
        try:
            from app.notify import notify_alerts
            notify_alerts(db, created_alerts, snapshot)
        except Exception:
            logger.exception("рассылка уведомлений не прошла")

    logger.info(
        "cam %s (%s): %d детекций, ROI отбросил %d, алертов создано %d",
        camera.id, camera.external_key or "-",
        len(verdict.detections), verdict.dropped_by_roi, len(created_alerts),
    )
    return IngestResult(snapshot=snapshot, created_alerts=created_alerts, verdict=verdict)


def _has_open_alert(db: Session, site_id: int, level: str) -> bool:
    return (
        db.query(Alert)
        .filter(Alert.site_id == site_id, Alert.level == level, Alert.status != "resolved")
        .first()
        is not None
    )
