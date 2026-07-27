from datetime import datetime

from pydantic import ConfigDict
from sqlmodel import SQLModel


class SnapshotPublic(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    captured_at: datetime
    s3_bucket: str
    s3_key: str
    width: int
    height: int
    file_size: int
    status: str
    error_message: str | None
    created_at: datetime
    image_url: str | None = None


class CaptureTrigger(SQLModel):
    camera_id: int
