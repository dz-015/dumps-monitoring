from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db.database import get_db
from app.db.models import Camera, Site, User
from app.schemas import CameraCreate, CameraOut

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


def _cam_to_out(cam: Camera, db: Session) -> dict:
    site = db.query(Site).filter(Site.id == cam.site_id).first()
    return {
        **{c.name: getattr(cam, c.name) for c in cam.__table__.columns},
        "site_name": site.name if site else "",
    }


def _scoped_cameras(query, user: User):
    """Non-admin users see only cameras on sites of their own organization."""
    if user.is_admin:
        return query
    return query.join(Site, Camera.site_id == Site.id).filter(
        Site.organization_id == user.organization_id
    )


def _get_camera_or_404(cam_id: int, db: Session, user: User) -> Camera:
    cam = _scoped_cameras(db.query(Camera).filter(Camera.id == cam_id), user).first()
    if not cam:
        raise HTTPException(404, "Camera not found")
    return cam


def _get_site_in_org_or_404(site_id: int, db: Session, user: User) -> Site:
    q = db.query(Site).filter(Site.id == site_id)
    if not user.is_admin:
        q = q.filter(Site.organization_id == user.organization_id)
    site = q.first()
    if not site:
        raise HTTPException(404, "Site not found")
    return site


@router.get("", response_model=list[CameraOut])
def list_cameras(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cams = _scoped_cameras(db.query(Camera), user).order_by(Camera.created_at.desc()).all()
    return [_cam_to_out(c, db) for c in cams]


@router.post("", response_model=CameraOut, status_code=201)
def create_camera(
    data: CameraCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    _get_site_in_org_or_404(data.site_id, db, user)
    cam = Camera(**data.model_dump())
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return _cam_to_out(cam, db)


@router.delete("/{camera_id}", status_code=204)
def delete_camera(
    camera_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    cam = _get_camera_or_404(camera_id, db, user)
    db.delete(cam)
    db.commit()
