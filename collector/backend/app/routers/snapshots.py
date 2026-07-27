from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.camera import Camera
from app.models.snapshot import Snapshot
from app.schemas.snapshot import CaptureTrigger, SnapshotPublic
from app.services.storage import storage

router = APIRouter()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _presigned_url(snapshot: Snapshot) -> str | None:
    """Generate a presigned URL for a snapshot with status='captured'."""
    if snapshot.status != "captured":
        return None
    return storage.get_presigned_url(snapshot.s3_bucket, snapshot.s3_key)


def _snapshot_with_url(snapshot: Snapshot) -> SnapshotPublic:
    public = SnapshotPublic.model_validate(snapshot)
    public.image_url = _presigned_url(snapshot)
    return public


@router.get(
    "/cameras/{camera_id}/snapshots/",
    response_model=list[SnapshotPublic],
    tags=["snapshots"],
)
async def list_snapshots(
    camera_id: int,
    session: SessionDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    camera = await session.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    query = (
        select(Snapshot)
        .where(Snapshot.camera_id == camera_id)
        .order_by(Snapshot.captured_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.exec(query)
    snapshots = result.all()
    return [_snapshot_with_url(s) for s in snapshots]


@router.get(
    "/snapshots/{snapshot_id}/",
    response_model=SnapshotPublic,
    tags=["snapshots"],
)
async def get_snapshot(snapshot_id: int, session: SessionDep):
    snapshot = await session.get(Snapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return _snapshot_with_url(snapshot)


@router.post(
    "/capture/trigger/",
    response_model=SnapshotPublic,
    status_code=201,
    tags=["capture"],
)
async def trigger_capture(body: CaptureTrigger, session: SessionDep):
    camera = await session.get(Camera, body.camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    from app.services.snapshot import capture_and_store

    snapshot = await capture_and_store(camera, session)
    return _snapshot_with_url(snapshot)
