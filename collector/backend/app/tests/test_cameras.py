import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _create_camera(
    client: AsyncClient,
    name: str = "Test Camera",
    rtsp_url: str = "rtsp://example.com/stream1",
    **kwargs,
) -> dict:
    payload = {"name": name, "rtsp_url": rtsp_url, **kwargs}
    response = await client.post("/api/v1/cameras/", json=payload)
    return response


async def test_create_camera(client: AsyncClient):
    response = await _create_camera(client)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["name"] == "Test Camera"
    assert data["rtsp_url"] == "rtsp://example.com/stream1"


async def test_create_camera_with_defaults(client: AsyncClient):
    response = await _create_camera(client)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "active"
    assert data["capture_interval_minutes"] == 60


async def test_create_camera_missing_fields(client: AsyncClient):
    response = await client.post("/api/v1/cameras/", json={})
    assert response.status_code == 422


async def test_list_cameras(client: AsyncClient):
    await _create_camera(client, name="Cam 1", rtsp_url="rtsp://example.com/1")
    await _create_camera(client, name="Cam 2", rtsp_url="rtsp://example.com/2")

    response = await client.get("/api/v1/cameras/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


async def test_list_cameras_filter_by_status(client: AsyncClient):
    await _create_camera(client, name="Active Cam", rtsp_url="rtsp://example.com/a")
    resp = await _create_camera(
        client, name="Inactive Cam", rtsp_url="rtsp://example.com/i"
    )
    cam_id = resp.json()["id"]
    await client.patch(f"/api/v1/cameras/{cam_id}/", json={"status": "inactive"})

    response = await client.get("/api/v1/cameras/", params={"status": "active"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Active Cam"


async def test_get_camera(client: AsyncClient):
    create_resp = await _create_camera(client)
    cam_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/cameras/{cam_id}/")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == cam_id
    assert data["name"] == "Test Camera"


async def test_get_camera_not_found(client: AsyncClient):
    response = await client.get("/api/v1/cameras/999/")
    assert response.status_code == 404


async def test_update_camera(client: AsyncClient):
    create_resp = await _create_camera(client)
    cam_id = create_resp.json()["id"]

    response = await client.patch(
        f"/api/v1/cameras/{cam_id}/",
        json={"name": "Updated Camera", "status": "inactive"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Camera"
    assert data["status"] == "inactive"


async def test_update_camera_partial(client: AsyncClient):
    create_resp = await _create_camera(
        client, name="Original", rtsp_url="rtsp://example.com/orig"
    )
    cam_id = create_resp.json()["id"]

    response = await client.patch(
        f"/api/v1/cameras/{cam_id}/", json={"name": "Changed"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Changed"
    assert data["rtsp_url"] == "rtsp://example.com/orig"
    assert data["status"] == "active"


async def test_delete_camera(client: AsyncClient):
    create_resp = await _create_camera(client)
    cam_id = create_resp.json()["id"]

    response = await client.delete(f"/api/v1/cameras/{cam_id}/")
    assert response.status_code == 204

    get_resp = await client.get(f"/api/v1/cameras/{cam_id}/")
    assert get_resp.status_code == 404
