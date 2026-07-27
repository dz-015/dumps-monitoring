from datetime import datetime, timezone

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.camera import Camera
from app.models.snapshot import Snapshot


pytestmark = pytest.mark.asyncio


async def test_camera_create_and_read(session: AsyncSession):
    camera = Camera(name="Test Camera", rtsp_url="rtsp://example.com/stream1")
    session.add(camera)
    await session.flush()
    await session.refresh(camera)

    assert camera.id is not None
    assert camera.name == "Test Camera"
    assert camera.rtsp_url == "rtsp://example.com/stream1"
    assert camera.status == "active"
    assert camera.capture_interval_minutes == 60
    assert camera.created_at is not None
    assert camera.updated_at is not None


async def test_camera_defaults(session: AsyncSession):
    camera = Camera(name="Cam 2", rtsp_url="rtsp://example.com/stream2")
    session.add(camera)
    await session.flush()
    await session.refresh(camera)

    assert camera.status == "active"
    assert camera.capture_interval_minutes == 60


async def test_camera_custom_status(session: AsyncSession):
    camera = Camera(
        name="Inactive Cam",
        rtsp_url="rtsp://example.com/stream3",
        status="inactive",
        capture_interval_minutes=30,
    )
    session.add(camera)
    await session.flush()
    await session.refresh(camera)

    assert camera.status == "inactive"
    assert camera.capture_interval_minutes == 30


async def test_snapshot_create_and_read(session: AsyncSession):
    camera = Camera(name="Snap Cam", rtsp_url="rtsp://example.com/snap")
    session.add(camera)
    await session.flush()
    await session.refresh(camera)

    now = datetime.now(timezone.utc)
    snapshot = Snapshot(
        camera_id=camera.id,
        captured_at=now,
        s3_key="snapshots/2026/02/19/cam1_001.jpg",
        width=1920,
        height=1080,
        file_size=256000,
    )
    session.add(snapshot)
    await session.flush()
    await session.refresh(snapshot)

    assert snapshot.id is not None
    assert snapshot.camera_id == camera.id
    assert snapshot.s3_bucket == "snapshots"
    assert snapshot.s3_key == "snapshots/2026/02/19/cam1_001.jpg"
    assert snapshot.width == 1920
    assert snapshot.height == 1080
    assert snapshot.file_size == 256000
    assert snapshot.status == "captured"
    assert snapshot.error_message is None
    assert snapshot.created_at is not None


async def test_snapshot_with_error(session: AsyncSession):
    camera = Camera(name="Error Cam", rtsp_url="rtsp://example.com/err")
    session.add(camera)
    await session.flush()
    await session.refresh(camera)

    now = datetime.now(timezone.utc)
    snapshot = Snapshot(
        camera_id=camera.id,
        captured_at=now,
        s3_key="snapshots/2026/02/19/cam_err.jpg",
        width=0,
        height=0,
        file_size=0,
        status="error",
        error_message="Connection timeout",
    )
    session.add(snapshot)
    await session.flush()
    await session.refresh(snapshot)

    assert snapshot.status == "error"
    assert snapshot.error_message == "Connection timeout"


async def test_snapshot_foreign_key(session: AsyncSession):
    camera = Camera(name="FK Cam", rtsp_url="rtsp://example.com/fk")
    session.add(camera)
    await session.flush()
    await session.refresh(camera)

    now = datetime.now(timezone.utc)
    snapshot = Snapshot(
        camera_id=camera.id,
        captured_at=now,
        s3_key="snapshots/fk_test.jpg",
        width=640,
        height=480,
        file_size=50000,
    )
    session.add(snapshot)
    await session.flush()

    result = await session.exec(
        select(Snapshot).where(Snapshot.camera_id == camera.id)
    )
    loaded = result.first()
    assert loaded is not None
    assert loaded.camera_id == camera.id
