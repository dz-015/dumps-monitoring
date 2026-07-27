from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db.database import get_db
from app.db.models import Site, Snapshot, User
from app.schemas import SnapshotOut

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])


@router.get("/{snapshot_id}", response_model=SnapshotOut)
def get_snapshot(
    snapshot_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Single snapshot with its detections — feeds the alert detail view."""
    q = db.query(Snapshot).filter(Snapshot.id == snapshot_id)
    if not user.is_admin:
        q = q.join(Site, Snapshot.site_id == Site.id).filter(
            Site.organization_id == user.organization_id
        )
    snap = q.first()
    if not snap:
        raise HTTPException(404, "Snapshot not found")
    return snap
