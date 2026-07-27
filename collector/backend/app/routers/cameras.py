from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.camera import Camera
from app.schemas.camera import CameraCreate, CameraPublic, CameraUpdate
from app.services.scheduler import add_camera_job, remove_camera_job

router = APIRouter()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("/", response_model=CameraPublic, status_code=201)
async def create_camera(camera_in: CameraCreate, session: SessionDep):
    camera = Camera.model_validate(camera_in)
    session.add(camera)
    await session.commit()
    await session.refresh(camera)
    add_camera_job(camera.id, camera.capture_interval_minutes)
    return camera


@router.get("/", response_model=list[CameraPublic])
async def list_cameras(
    session: SessionDep,
    status: str | None = Query(default=None),
):
    query = select(Camera)
    if status is not None:
        query = query.where(Camera.status == status)
    result = await session.exec(query)
    return result.all()


@router.get("/{camera_id}/", response_model=CameraPublic)
async def get_camera(camera_id: int, session: SessionDep):
    camera = await session.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


@router.patch("/{camera_id}/", response_model=CameraPublic)
async def update_camera(
    camera_id: int, camera_in: CameraUpdate, session: SessionDep
):
    camera = await session.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    update_data = camera_in.model_dump(exclude_unset=True)
    camera.sqlmodel_update(update_data)
    session.add(camera)
    await session.commit()
    await session.refresh(camera)
    if camera.status == "inactive":
        remove_camera_job(camera.id)
    elif camera.status == "active":
        add_camera_job(camera.id, camera.capture_interval_minutes)
    return camera


@router.delete("/{camera_id}/", status_code=204)
async def delete_camera(camera_id: int, session: SessionDep):
    camera = await session.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    await session.delete(camera)
    await session.commit()
    remove_camera_job(camera.id)
