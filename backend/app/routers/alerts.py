import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db.database import get_db
from app.db.models import Alert, Site, User
from app.schemas import ALLOWED_RESOLUTION_REASONS, AlertOut, AlertStatusUpdate

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def _scoped(query, user: User):
    """Non-admin users see only alerts on sites of their own organization."""
    if user.is_admin:
        return query
    return query.join(Site, Alert.site_id == Site.id).filter(
        Site.organization_id == user.organization_id
    )


@router.get("")
def list_alerts(
    level: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = _scoped(db.query(Alert), user)
    if level:
        q = q.filter(Alert.level == level)
    if status:
        q = q.filter(Alert.status == status)
    total = q.count()
    alerts = q.order_by(Alert.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    items = []
    for a in alerts:
        site = db.query(Site).filter(Site.id == a.site_id).first()
        items.append(
            {
                **{c.name: getattr(a, c.name) for c in a.__table__.columns},
                "site_name": site.name if site else "",
            }
        )
    return {"items": items, "total": total}


@router.patch("/{alert_id}", response_model=AlertOut)
def update_alert_status(
    alert_id: int,
    data: AlertStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    alert = _scoped(db.query(Alert).filter(Alert.id == alert_id), user).first()
    if not alert:
        raise HTTPException(404, "Alert not found")

    if data.status == "resolved":
        if not data.resolution_reason:
            raise HTTPException(400, "resolution_reason is required when resolving an alert")
        if data.resolution_reason not in ALLOWED_RESOLUTION_REASONS:
            raise HTTPException(
                400,
                f"resolution_reason must be one of {sorted(ALLOWED_RESOLUTION_REASONS)}",
            )
        alert.resolution_reason = data.resolution_reason
        alert.resolved_at = dt.datetime.now(dt.UTC)
    else:
        if data.resolution_reason is not None:
            raise HTTPException(
                400, "resolution_reason is only valid when status=resolved"
            )
        alert.resolution_reason = None
        alert.resolved_at = None

    alert.status = data.status
    db.commit()
    db.refresh(alert)
    site = db.query(Site).filter(Site.id == alert.site_id).first()
    return {
        **{c.name: getattr(alert, c.name) for c in alert.__table__.columns},
        "site_name": site.name if site else "",
    }
