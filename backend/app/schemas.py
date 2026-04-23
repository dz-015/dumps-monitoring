import datetime as dt
from pydantic import BaseModel, EmailStr


# ── Auth ──────────────────────────────────────────────
class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str = ""

class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
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
    created_at: dt.datetime
    camera_count: int = 0
    class Config:
        from_attributes = True


# ── Cameras ───────────────────────────────────────────
class CameraCreate(BaseModel):
    site_id: int
    name: str
    rtsp_url: str

class CameraOut(BaseModel):
    id: int
    site_id: int
    name: str
    rtsp_url: str
    is_active: bool
    last_checked: dt.datetime | None
    created_at: dt.datetime
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
    created_at: dt.datetime
    resolved_at: dt.datetime | None
    site_name: str = ""
    class Config:
        from_attributes = True

class AlertStatusUpdate(BaseModel):
    status: str  # new | accepted | resolved


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
    taken_at: dt.datetime
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
