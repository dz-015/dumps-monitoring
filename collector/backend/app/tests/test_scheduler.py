from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.services.scheduler import (
    _job_id,
    add_camera_job,
    remove_camera_job,
    scheduler,
    start_scheduler,
    stop_scheduler,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(autouse=True)
async def _clean_scheduler():
    """Remove all jobs before and after each test."""
    scheduler.remove_all_jobs()
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)
    scheduler.remove_all_jobs()


async def test_add_camera_job():
    add_camera_job(1, interval_minutes=15)

    job = scheduler.get_job(_job_id(1))
    assert job is not None
    assert job.id == "capture_camera_1"


async def test_add_camera_job_replaces_existing():
    add_camera_job(1, interval_minutes=15)
    add_camera_job(1, interval_minutes=30)

    jobs = scheduler.get_jobs()
    matching = [j for j in jobs if j.id == _job_id(1)]
    assert len(matching) == 1


async def test_remove_camera_job():
    add_camera_job(1, interval_minutes=15)
    assert scheduler.get_job(_job_id(1)) is not None

    remove_camera_job(1)
    assert scheduler.get_job(_job_id(1)) is None


async def test_remove_camera_job_nonexistent():
    # Should not raise
    remove_camera_job(999)


@patch("app.services.scheduler.async_session")
async def test_start_scheduler_loads_cameras(mock_async_session):
    cam1 = MagicMock()
    cam1.id = 1
    cam1.capture_interval_minutes = 10

    cam2 = MagicMock()
    cam2.id = 2
    cam2.capture_interval_minutes = 30

    mock_result = MagicMock()
    mock_result.all.return_value = [cam1, cam2]

    mock_session = AsyncMock()
    mock_session.exec.return_value = mock_result
    mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

    await start_scheduler()

    assert scheduler.get_job(_job_id(1)) is not None
    assert scheduler.get_job(_job_id(2)) is not None
    assert scheduler.running


@patch("app.services.scheduler.capture_and_store", new_callable=AsyncMock)
@patch("app.services.scheduler.async_session")
async def test_capture_job_calls_capture_and_store(
    mock_async_session, mock_capture_and_store
):
    from app.services.scheduler import _capture_job

    mock_camera = MagicMock()
    mock_camera.status = "active"

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_camera
    mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_snapshot = MagicMock()
    mock_snapshot.id = 42
    mock_capture_and_store.return_value = mock_snapshot

    await _capture_job(1)

    mock_capture_and_store.assert_awaited_once_with(mock_camera, mock_session)


@patch("app.services.scheduler.async_session")
async def test_capture_job_skips_inactive_camera(mock_async_session):
    from app.services.scheduler import _capture_job

    mock_camera = MagicMock()
    mock_camera.status = "inactive"

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_camera
    mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

    # Should not raise, just skip
    await _capture_job(1)


@patch("app.services.scheduler.capture_and_store", new_callable=AsyncMock)
@patch("app.services.scheduler.async_session")
async def test_capture_job_handles_capture_error(
    mock_async_session, mock_capture_and_store
):
    from app.services.scheduler import _capture_job

    mock_camera = MagicMock()
    mock_camera.status = "active"

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_camera
    mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_capture_and_store.side_effect = ConnectionError("Camera offline")

    # Should not raise -- errors are caught inside _capture_job
    await _capture_job(1)
