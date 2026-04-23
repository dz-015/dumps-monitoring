from contextlib import asynccontextmanager
from backend.app.routers import alerts, auth, cameras, dashboard, predict, sites
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.db.database import engine, SessionLocal, Base
from backend.app.db.models import *  # noqa: ensure all models are registered
from backend.app.seed import seed_db
from backend.app.routers import snapshots


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables
    Base.metadata.create_all(bind=engine)
    # Seed demo data
    db = SessionLocal()
    try:
        seed_db(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="НЭКОБАК API",
    description="API for waste container monitoring system",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
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
app.include_router(predict.router)
app.include_router(snapshots.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
