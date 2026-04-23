import datetime as dt
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.db.database import get_db
from app.db.models import Site, Camera, Alert
from app.schemas import DashboardStats
from app.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db), _=Depends(get_current_user)):
    total_sites = db.query(func.count(Site.id)).scalar() or 0
    active_cameras = db.query(func.count(Camera.id)).filter(Camera.is_active == True).scalar() or 0
    open_alerts = db.query(func.count(Alert.id)).filter(Alert.status != "resolved").scalar() or 0

    status_counts = {}
    for status_val in ["clean", "overflow", "contamination"]:
        cnt = db.query(func.count(Site.id)).filter(Site.status == status_val).scalar() or 0
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
def problems_last_week(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Daily alert counts for the last 7 days."""
    now = dt.datetime.now(dt.timezone.utc)
    week_ago = now - dt.timedelta(days=7)
    rows = (
        db.query(
            func.date(Alert.created_at).label("day"),
            func.count(Alert.id).label("count"),
        )
        .filter(Alert.created_at >= week_ago)
        .group_by(func.date(Alert.created_at))
        .order_by(func.date(Alert.created_at))
        .all()
    )
    return [{"day": str(r.day), "count": r.count} for r in rows]


@router.get("/problems-month")
def problems_last_month(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Daily alert counts for the last 31 days."""
    now = dt.datetime.now(dt.timezone.utc)
    month_ago = now - dt.timedelta(days=31)
    rows = (
        db.query(
            func.date(Alert.created_at).label("day"),
            func.count(Alert.id).label("count"),
        )
        .filter(Alert.created_at >= month_ago)
        .group_by(func.date(Alert.created_at))
        .order_by(func.date(Alert.created_at))
        .all()
    )
    return [{"day": str(r.day), "count": r.count} for r in rows]
