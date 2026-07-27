from unittest.mock import patch

import numpy as np
import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.camera import Camera
from app.services.snapshot import capture_and_store
from app.services.storage import StorageService

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _ensure_test_bucket():
    """Create bucket in local MinIO for tests (prod buckets are pre-created)."""
    from app.config import settings

    service = StorageService()
    bucket = settings.s3_snapshots_bucket
    try:
        service.client.head_bucket(Bucket=bucket)
    except Exception:
        service.client.create_bucket(Bucket=bucket)


def _make_test_jpeg() -> tuple[bytes, int, int]:
    """Create a real JPEG from a numpy array to simulate capture output."""
    import cv2

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[100:200, 100:300] = (0, 255, 0)  # Green rectangle
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return buf.tobytes(), 640, 480


async def test_capture_and_store_success(session: AsyncSession):
    camera = Camera(name="Test Cam", rtsp_url="rtsp://example.com/test")
    session.add(camera)
    await session.flush()
    await session.refresh(camera)

    jpeg_data, width, height = _make_test_jpeg()

    with patch("app.services.snapshot.capture_frame", return_value=(jpeg_data, width, height)):
        snapshot = await capture_and_store(camera, session)

    assert snapshot.id is not None
    assert snapshot.camera_id == camera.id
    assert snapshot.status == "captured"
    assert snapshot.width == 640
    assert snapshot.height == 480
    assert snapshot.file_size == len(jpeg_data)
    assert snapshot.s3_key.startswith(f"cameras/{camera.id}/")
    assert snapshot.s3_key.endswith(".jpg")
    assert snapshot.error_message is None

    # Verify file actually exists in S3
    from app.config import settings
    from app.services.storage import storage

    response = storage.client.head_object(
        Bucket=settings.s3_snapshots_bucket, Key=snapshot.s3_key,
    )
    assert response["ContentLength"] == len(jpeg_data)

    # Cleanup
    storage.client.delete_object(
        Bucket=settings.s3_snapshots_bucket, Key=snapshot.s3_key,
    )


async def test_capture_and_store_capture_failure(session: AsyncSession):
    camera = Camera(name="Failing Cam", rtsp_url="rtsp://example.com/fail")
    session.add(camera)
    await session.flush()
    await session.refresh(camera)

    with patch(
        "app.services.snapshot.capture_frame",
        side_effect=RuntimeError("Connection timeout"),
    ):
        snapshot = await capture_and_store(camera, session)

    assert snapshot.id is not None
    assert snapshot.camera_id == camera.id
    assert snapshot.status == "error"
    assert snapshot.error_message == "Connection timeout"
    assert snapshot.s3_key == ""
    assert snapshot.width == 0
    assert snapshot.height == 0
    assert snapshot.file_size == 0

    # Camera status should be set to error
    await session.refresh(camera)
    assert camera.status == "error"
