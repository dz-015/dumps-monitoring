import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, PlainSerializer


def _to_utc_iso(v: dt.datetime) -> str:
    """DB stores naive-UTC datetimes; stamp the offset so browsers don't
    reinterpret them as local time (BUG-09)."""
    if v.tzinfo is None:
        v = v.replace(tzinfo=dt.UTC)
    return v.isoformat()


UTCDateTime = Annotated[dt.datetime, PlainSerializer(_to_utc_iso, return_type=str)]


# ── Auth ──────────────────────────────────────────────
class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str = ""
    organization_name: str | None = None  # create a new org
    join_code: str | None = None  # or join an existing one


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    is_admin: bool = False
    organization_id: int | None = None
    avatar_path: str | None = None
    telegram_connected: bool = False
    max_connected: bool = False

    class Config:
        from_attributes = True


class TelegramStatus(BaseModel):
    # enabled=False — на сервере не настроен токен бота, кнопку не показываем.
    enabled: bool
    connected: bool
    link: str | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None


class OrganizationOut(BaseModel):
    id: int
    name: str
    join_code: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: str
    password: str


# ── Sites ─────────────────────────────────────────────
class SiteCreate(BaseModel):
    name: str
    address: str = ""
    latitude: float | None = None
    longitude: float | None = None


class SiteUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class SiteOut(BaseModel):
    id: int
    name: str
    address: str
    latitude: float | None
    longitude: float | None
    status: str
    created_at: UTCDateTime
    camera_count: int = 0
    last_checked: UTCDateTime | None = None
    active_status: str | None = None

    class Config:
        from_attributes = True


# ── Cameras ───────────────────────────────────────────
class CameraCreate(BaseModel):
    site_id: int
    name: str
    rtsp_url: str
    external_key: str | None = None


class CameraUpdate(BaseModel):
    name: str | None = None
    rtsp_url: str | None = None
    external_key: str | None = None
    is_active: bool | None = None


class CameraOut(BaseModel):
    id: int
    site_id: int
    name: str
    rtsp_url: str
    external_key: str | None = None
    is_active: bool
    last_checked: UTCDateTime | None
    created_at: UTCDateTime
    site_name: str = ""

    class Config:
        from_attributes = True


# ── Alerts ────────────────────────────────────────────
class AlertOut(BaseModel):
    id: int
    site_id: int
    snapshot_id: int | None
    level: str
    status: str
    resolution_reason: str | None = None
    created_at: UTCDateTime
    resolved_at: UTCDateTime | None
    site_name: str = ""

    class Config:
        from_attributes = True


class AlertListOut(BaseModel):
    items: list[AlertOut]
    total: int


ALLOWED_RESOLUTION_REASONS = {"confirmed_and_cleared", "false_alarm", "resolved_externally"}


class AlertStatusUpdate(BaseModel):
    status: Literal["new", "accepted", "resolved"]
    # Required when status=resolved, forbidden otherwise. Validated in the router
    # rather than the schema so we can return a specific 400 message.
    resolution_reason: str | None = None


# ── Detections ────────────────────────────────────────
class DetectionOut(BaseModel):
    id: int
    class_name: str
    confidence: float
    x: float
    y: float
    w: float
    h: float

    class Config:
        from_attributes = True


# ── Snapshots ─────────────────────────────────────────
class SnapshotOut(BaseModel):
    id: int
    site_id: int
    camera_id: int
    image_path: str
    taken_at: UTCDateTime
    detections: list[DetectionOut] = []

    class Config:
        from_attributes = True


# ── Dashboard ─────────────────────────────────────────
class DashboardStats(BaseModel):
    total_sites: int
    active_cameras: int
    open_alerts: int
    clean_percent: float
    status_counts: dict[str, int]  # {"clean": X, "overflow": Y, "contamination": Z}


# ── Predict (ML) ──────────────────────────────────────
class PredictionBox(BaseModel):
    class_name: str
    confidence: float
    x: float
    y: float
    w: float
    h: float


class PredictResponse(BaseModel):
    detections: list[PredictionBox]
    has_overflow: bool
    has_contamination: bool


# ── Pagination ────────────────────────────────────────
class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    per_page: int
    pages: int
