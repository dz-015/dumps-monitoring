import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db.database import get_db
from app.db.models import Alert, Camera, Site, Snapshot, User
from app.schemas import AlertOut, SiteCreate, SiteOut, SiteUpdate, SnapshotOut

router = APIRouter(prefix="/api/sites", tags=["sites"])


def _site_to_out(site: Site, db: Session) -> dict:
    cam_count = db.query(func.count(Camera.id)).filter(Camera.site_id == site.id).scalar()
    last_checked = (
        db.query(func.max(Camera.last_checked)).filter(Camera.site_id == site.id).scalar()
    )
    active_status = _derive_active_status(site, db)
    return {
        **{c.name: getattr(site, c.name) for c in site.__table__.columns},
        "camera_count": cam_count,
        "last_checked": last_checked,
        "active_status": active_status,
    }


def _derive_active_status(site: Site, db: Session) -> str:
    """Unresolved overflow beats unresolved contamination; else fall back to site.status."""
    unresolved = (
        db.query(Alert.level)
        .filter(Alert.site_id == site.id, Alert.status != "resolved")
        .all()
    )
    levels = {row[0] for row in unresolved}
    if "overflow" in levels:
        return "overflow"
    if "contamination" in levels:
        return "contamination"
    return site.status


def _scoped(query, user: User):
    """Non-admin users see only their own org's sites."""
    if user.is_admin:
        return query
    return query.filter(Site.organization_id == user.organization_id)


def _get_site_or_404(site_id: int, db: Session, user: User) -> Site:
    site = _scoped(db.query(Site).filter(Site.id == site_id), user).first()
    if not site:
        raise HTTPException(404, "Site not found")
    return site


@router.get("", response_model=list[SiteOut])
def list_sites(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sites = _scoped(db.query(Site), user).order_by(Site.name).all()
    return [_site_to_out(s, db) for s in sites]


@router.get("/{site_id}", response_model=SiteOut)
def get_site(site_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    site = _get_site_or_404(site_id, db, user)
    return _site_to_out(site, db)


@router.post("", response_model=SiteOut, status_code=201)
def create_site(
    data: SiteCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    if user.organization_id is None:
        raise HTTPException(400, "User has no organization — cannot create a site")
    site = Site(**data.model_dump(), organization_id=user.organization_id)
    db.add(site)
    db.commit()
    db.refresh(site)
    return _site_to_out(site, db)


@router.patch("/{site_id}", response_model=SiteOut)
def update_site(
    site_id: int,
    data: SiteUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    site = _get_site_or_404(site_id, db, user)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(site, k, v)
    db.commit()
    db.refresh(site)
    return _site_to_out(site, db)


@router.delete("/{site_id}", status_code=204)
def delete_site(
    site_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    site = _get_site_or_404(site_id, db, user)
    db.query(Snapshot).filter(Snapshot.site_id == site_id).delete()
    db.query(Alert).filter(Alert.site_id == site_id).delete()
    db.query(Camera).filter(Camera.site_id == site_id).delete()
    db.delete(site)
    db.commit()


@router.get("/{site_id}/snapshots", response_model=list[SnapshotOut])
def get_site_snapshots(
    site_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _get_site_or_404(site_id, db, user)
    return (
        db.query(Snapshot)
        .filter(Snapshot.site_id == site_id)
        .order_by(Snapshot.taken_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/{site_id}/alerts", response_model=list[AlertOut])
def get_site_alerts(
    site_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    site = _get_site_or_404(site_id, db, user)
    alerts = (
        db.query(Alert)
        .filter(Alert.site_id == site_id)
        .order_by(Alert.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {**{c.name: getattr(a, c.name) for c in a.__table__.columns}, "site_name": site.name}
        for a in alerts
    ]


@router.get("/{site_id}/problems-week")
def get_site_problems_week(
    site_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _get_site_or_404(site_id, db, user)
    return _site_problems_since(db, site_id, days=7)


@router.get("/{site_id}/problems-month")
def get_site_problems_month(
    site_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _get_site_or_404(site_id, db, user)
    return _site_problems_since(db, site_id, days=31)


def _site_problems_since(db: Session, site_id: int, days: int) -> list[dict]:
    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
    rows = (
        db.query(
            func.date(Alert.created_at).label("day"),
            func.count(Alert.id).label("count"),
        )
        .filter(Alert.site_id == site_id, Alert.created_at >= since)
        .group_by(func.date(Alert.created_at))
        .order_by(func.date(Alert.created_at))
        .all()
    )
    return [{"day": str(r.day), "count": r.count} for r in rows]
