from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.database import get_db
from app.db.models import Site, Camera, Alert, Snapshot, Detection
from app.schemas import SiteCreate, SiteUpdate, SiteOut, SnapshotOut, DetectionOut, AlertOut
from app.auth import get_current_user

router = APIRouter(prefix="/api/sites", tags=["sites"])


def _site_to_out(site: Site, db: Session) -> dict:
    cam_count = db.query(func.count(Camera.id)).filter(Camera.site_id == site.id).scalar()
    return {
        **{c.name: getattr(site, c.name) for c in site.__table__.columns},
        "camera_count": cam_count,
    }


@router.get("", response_model=list[SiteOut])
def list_sites(db: Session = Depends(get_db), _=Depends(get_current_user)):
    sites = db.query(Site).order_by(Site.name).all()
    return [_site_to_out(s, db) for s in sites]


@router.get("/{site_id}", response_model=SiteOut)
def get_site(site_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(404, "Site not found")
    return _site_to_out(site, db)


@router.post("", response_model=SiteOut, status_code=201)
def create_site(data: SiteCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    site = Site(**data.model_dump())
    db.add(site)
    db.commit()
    db.refresh(site)
    return _site_to_out(site, db)


@router.patch("/{site_id}", response_model=SiteOut)
def update_site(site_id: int, data: SiteUpdate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(404, "Site not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(site, k, v)
    db.commit()
    db.refresh(site)
    return _site_to_out(site, db)


@router.delete("/{site_id}", status_code=204)
def delete_site(site_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(404, "Site not found")
    db.delete(site)
    db.commit()


@router.get("/{site_id}/snapshots", response_model=list[SnapshotOut])
def get_site_snapshots(
    site_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    snaps = (
        db.query(Snapshot)
        .filter(Snapshot.site_id == site_id)
        .order_by(Snapshot.taken_at.desc())
        .limit(limit)
        .all()
    )
    return snaps


@router.get("/{site_id}/alerts", response_model=list[AlertOut])
def get_site_alerts(
    site_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    alerts = (
        db.query(Alert)
        .filter(Alert.site_id == site_id)
        .order_by(Alert.created_at.desc())
        .limit(limit)
        .all()
    )
    site = db.query(Site).filter(Site.id == site_id).first()
    return [
        {**{c.name: getattr(a, c.name) for c in a.__table__.columns}, "site_name": site.name if site else ""}
        for a in alerts
    ]
