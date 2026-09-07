import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.database import async_session
from app.models.camera import Camera
from app.services.snapshot import capture_and_store

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def _job_id(camera_id: int) -> str:
    return f"capture_camera_{camera_id}"


async def _capture_job(camera_id: int) -> None:
    """Capture frame from camera and store it."""
    async with async_session() as session:
        camera = await session.get(Camera, camera_id)
        if camera is None or camera.status == "inactive":
            logger.warning(
                "Skipping capture for camera %s: not found or inactive",
                camera_id,
            )
            return
        try:
            snapshot = await capture_and_store(camera, session)
            logger.info(
                "Captured snapshot %s from camera %s", snapshot.id, camera_id
            )
        except Exception:
            logger.exception("Capture job failed for camera %s", camera_id)


def add_camera_job(camera_id: int, interval_minutes: int) -> None:
    """Add or replace capture job for a camera."""
    job_id = _job_id(camera_id)
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    scheduler.add_job(
        _capture_job,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id=job_id,
        args=[camera_id],
        next_run_time=datetime.now(timezone.utc),
        replace_existing=True,
    )
    logger.info(
        "Scheduled capture for camera %s every %s minutes",
        camera_id,
        interval_minutes,
    )


def remove_camera_job(camera_id: int) -> None:
    """Remove capture job for a camera."""
    job_id = _job_id(camera_id)
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info("Removed capture job for camera %s", camera_id)


async def start_scheduler() -> None:
    """Load active cameras and start scheduler."""
    from sqlmodel import select

    async with async_session() as session:
        # "error" cameras self-heal on the next successful capture, so they
        # must be scheduled too — otherwise a restart while a camera is down
        # silences it forever. Only explicitly "inactive" ones stay off.
        result = await session.exec(
            select(Camera).where(Camera.status != "inactive")
        )
        cameras = result.all()

    for camera in cameras:
        add_camera_job(camera.id, camera.capture_interval_minutes)

    scheduler.start()
    logger.info("Scheduler started with %s camera jobs", len(cameras))


def stop_scheduler() -> None:
    """Shutdown scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
