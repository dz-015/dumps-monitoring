from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os

from app.db.database import get_db
from app.db.models import Snapshot
from app.config import settings

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])


@router.get("/{snapshot_id}/image")
def get_snapshot_image(snapshot_id: int, db: Session = Depends(get_db)):
    snap = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
    if not snap or not os.path.exists(snap.image_path):
        # Return a placeholder
        return {"error": "Image not found"}
    return FileResponse(snap.image_path, media_type="image/jpeg")
