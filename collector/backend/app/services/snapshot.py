import asyncio
import logging
from datetime import datetime, timezone

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.camera import Camera
from app.models.snapshot import Snapshot
from app.services.capture import capture_frame
from app.services.storage import storage

logger = logging.getLogger(__name__)


async def capture_and_store(camera: Camera, session: AsyncSession) -> Snapshot:
    """
    Capture frame from camera, store in MinIO, create DB record.

    On success, ensures camera.status == "active" (recovering from a previous
    error). On failure, creates an error snapshot record and sets camera status
    to "error".
    """
    now = datetime.now(timezone.utc)

    try:
        jpeg_data, width, height = await asyncio.to_thread(
            capture_frame, camera.rtsp_url
        )

        s3_key = await asyncio.to_thread(
            storage.upload_snapshot, camera.id, now, jpeg_data
        )

        snapshot = Snapshot(
            camera_id=camera.id,
            captured_at=now,
            s3_key=s3_key,
            width=width,
            height=height,
            file_size=len(jpeg_data),
            status="captured",
        )

        if camera.status != "active":
            camera.status = "active"
            session.add(camera)
    except Exception as e:
        logger.error("Capture failed for camera %s: %s", camera.id, e)
        snapshot = Snapshot(
            camera_id=camera.id,
            captured_at=now,
            s3_key="",
            width=0,
            height=0,
            file_size=0,
            status="error",
            error_message=str(e),
        )
        camera.status = "error"
        session.add(camera)

    session.add(snapshot)
    await session.commit()
    await session.refresh(snapshot)
    return snapshot
