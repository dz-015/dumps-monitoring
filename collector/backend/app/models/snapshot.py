from datetime import datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class Snapshot(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    camera_id: int = Field(foreign_key="camera.id", index=True)
    captured_at: datetime = Field(
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            index=True,
            nullable=False,
        ),
    )
    s3_bucket: str = Field(default="snapshots")
    s3_key: str
    width: int
    height: int
    file_size: int
    status: str = Field(default="captured")
    error_message: str | None = Field(default=None)
    created_at: datetime | None = Field(
        default=None,
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
