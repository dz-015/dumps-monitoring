from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.camera import Camera
from app.models.snapshot import Snapshot

pytestmark = pytest.mark.asyncio

FAKE_PRESIGNED_URL = "http://s3.example.com/snapshots/test.jpg?signed=1"


@pytest.fixture(autouse=True)
def _mock_storage():
    with patch(
        "app.services.storage.storage.get_presigned_url",
        return_value=FAKE_PRESIGNED_URL,
    ):
        yield


async def _create_camera(session: AsyncSession, **kwargs) -> Camera:
    defaults = {"name": "Test Camera", "rtsp_url": "rtsp://example.com/stream1"}
    defaults.update(kwargs)
    camera = Camera(**defaults)
    session.add(camera)
    await session.flush()
    await session.refresh(camera)
    return camera


async def _create_snapshot(
    session: AsyncSession, camera_id: int, **kwargs
) -> Snapshot:
    defaults = {
        "camera_id": camera_id,
        "captured_at": datetime.now(timezone.utc),
        "s3_key": "snapshots/2026/02/19/test.jpg",
        "width": 1920,
        "height": 1080,
        "file_size": 256000,
    }
    defaults.update(kwargs)
    snapshot = Snapshot(**defaults)
    session.add(snapshot)
    await session.flush()
    await session.refresh(snapshot)
    return snapshot


async def test_list_snapshots_empty(
    client: AsyncClient, session: AsyncSession,
):
    camera = await _create_camera(session)
    await session.commit()

    response = await client.get(f"/api/v1/cameras/{camera.id}/snapshots/")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_snapshots_camera_not_found(client: AsyncClient):
    response = await client.get("/api/v1/cameras/999/snapshots/")
    assert response.status_code == 404


async def test_get_snapshot_not_found(client: AsyncClient):
    response = await client.get("/api/v1/snapshots/999/")
    assert response.status_code == 404


async def test_list_snapshots_with_data(
    client: AsyncClient, session: AsyncSession,
):
    camera = await _create_camera(session)
    snap = await _create_snapshot(session, camera.id)
    await session.commit()

    response = await client.get(f"/api/v1/cameras/{camera.id}/snapshots/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == snap.id
    assert data[0]["camera_id"] == camera.id
    assert data[0]["width"] == 1920
    assert data[0]["height"] == 1080
    assert data[0]["status"] == "captured"
    assert data[0]["image_url"] == FAKE_PRESIGNED_URL


async def test_list_snapshots_pagination(
    client: AsyncClient, session: AsyncSession,
):
    camera = await _create_camera(session)
    for i in range(5):
        await _create_snapshot(
            session,
            camera.id,
            s3_key=f"snapshots/2026/02/19/test_{i}.jpg",
        )
    await session.commit()

    response = await client.get(
        f"/api/v1/cameras/{camera.id}/snapshots/",
        params={"skip": 0, "limit": 2},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = await client.get(
        f"/api/v1/cameras/{camera.id}/snapshots/",
        params={"skip": 4, "limit": 10},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


async def test_get_snapshot(
    client: AsyncClient, session: AsyncSession,
):
    camera = await _create_camera(session)
    snap = await _create_snapshot(session, camera.id)
    await session.commit()

    response = await client.get(f"/api/v1/snapshots/{snap.id}/")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == snap.id
    assert data["camera_id"] == camera.id
    assert data["s3_key"] == "snapshots/2026/02/19/test.jpg"
    assert data["image_url"] == FAKE_PRESIGNED_URL


async def test_get_snapshot_error_status_no_image_url(
    client: AsyncClient, session: AsyncSession,
):
    camera = await _create_camera(session)
    snap = await _create_snapshot(
        session,
        camera.id,
        status="error",
        error_message="Connection timeout",
        width=0,
        height=0,
        file_size=0,
    )
    await session.commit()

    response = await client.get(f"/api/v1/snapshots/{snap.id}/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert data["error_message"] == "Connection timeout"
    assert data["image_url"] is None
