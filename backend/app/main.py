from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db.models import *  # noqa: F401,F403  registers all models with Base.metadata
from app.routers import (
    alerts,
    auth,
    cameras,
    dashboard,
    notifications,
    predict,
    sites,
    snapshots,
)

app = FastAPI(
    title="ТКО | Мониторинг API",
    description="API for waste container monitoring system",
    version="0.1.0",
)

# CORS — explicit origins required for credentialed requests; the "*" + credentials
# combo is rejected by browsers anyway. Override via CORS_ORIGINS env in prod.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for uploaded images
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Routers
app.include_router(auth.router)
app.include_router(sites.router)
app.include_router(cameras.router)
app.include_router(alerts.router)
app.include_router(dashboard.router)
app.include_router(snapshots.router)
app.include_router(predict.router)
app.include_router(notifications.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
