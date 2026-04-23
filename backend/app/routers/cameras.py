from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Camera, Site
from app.schemas import CameraCreate, CameraOut
from app.auth import get_current_user

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


def _cam_to_out(cam: Camera, db: Session) -> dict:
    site = db.query(Site).filter(Site.id == cam.site_id).first()
    return {
        **{c.name: getattr(cam, c.name) for c in cam.__table__.columns},
        "site_name": site.name if site else "",
    }


@router.get("", response_model=list[CameraOut])
def list_cameras(db: Session = Depends(get_db), _=Depends(get_current_user)):
    cams = db.query(Camera).order_by(Camera.created_at.desc()).all()
    return [_cam_to_out(c, db) for c in cams]


@router.post("", response_model=CameraOut, status_code=201)
def create_camera(data: CameraCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    site = db.query(Site).filter(Site.id == data.site_id).first()
    if not site:
        raise HTTPException(404, "Site not found")
    cam = Camera(**data.model_dump())
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return _cam_to_out(cam, db)


@router.delete("/{camera_id}", status_code=204)
def delete_camera(camera_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")
    db.delete(cam)
    db.commit()
