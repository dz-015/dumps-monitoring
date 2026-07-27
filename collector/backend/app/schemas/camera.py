from datetime import datetime

from pydantic import ConfigDict
from sqlmodel import SQLModel


class CameraCreate(SQLModel):
    name: str
    rtsp_url: str
    capture_interval_minutes: int = 60


class CameraUpdate(SQLModel):
    name: str | None = None
    rtsp_url: str | None = None
    status: str | None = None
    capture_interval_minutes: int | None = None


class CameraPublic(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    rtsp_url: str
    status: str
    capture_interval_minutes: int
    created_at: datetime
    updated_at: datetime
