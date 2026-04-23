import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db.database import get_db
from app.db.models import Alert, Camera, Site, User
from app.schemas import DashboardStats

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _site_scope(query, user: User):
    if user.is_admin:
        return query
    return query.filter(Site.organization_id == user.organization_id)


def _join_site_scope(query, user: User):
    """For Camera/Alert queries joining to Site."""
    if user.is_admin:
        return query
    return query.join(Site).filter(Site.organization_id == user.organization_id)


@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    total_sites = _site_scope(db.query(func.count(Site.id)), user).scalar() or 0

    cam_q = db.query(func.count(Camera.id)).filter(Camera.is_active == True)  # noqa: E712
    active_cameras = _join_site_scope(cam_q, user).scalar() or 0

    alert_q = db.query(func.count(Alert.id)).filter(Alert.status != "resolved")
    open_alerts = _join_site_scope(alert_q, user).scalar() or 0

    status_counts = {}
    for status_val in ["clean", "overflow", "contamination"]:
        cnt = (
            _site_scope(
                db.query(func.count(Site.id)).filter(Site.status == status_val), user
            ).scalar()
            or 0
        )
        status_counts[status_val] = cnt

    clean_pct = (status_counts.get("clean", 0) / total_sites * 100) if total_sites else 0

    return DashboardStats(
        total_sites=total_sites,
        active_cameras=active_cameras,
        open_alerts=open_alerts,
        clean_percent=round(clean_pct, 1),
        status_counts=status_counts,
    )


@router.get("/problems-week")
def problems_last_week(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _problems_since(db, user, days=7)


@router.get("/problems-month")
def problems_last_month(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _problems_since(db, user, days=31)


def _problems_since(db: Session, user: User, days: int):
    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
    q = db.query(
        func.date(Alert.created_at).label("day"),
        func.count(Alert.id).label("count"),
    ).filter(Alert.created_at >= since)
    q = _join_site_scope(q, user)
    rows = q.group_by(func.date(Alert.created_at)).order_by(func.date(Alert.created_at)).all()
    return [{"day": str(r.day), "count": r.count} for r in rows]
