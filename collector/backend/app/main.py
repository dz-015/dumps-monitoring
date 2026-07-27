import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.services.scheduler import start_scheduler, stop_scheduler
from app.services.storage import storage

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup
    await asyncio.to_thread(storage.check_connection)
    await start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


app = FastAPI(
    title="Waste Monitoring API",
    debug=settings.debug,
    lifespan=lifespan,
)


from app.routers import cameras, snapshots

app.include_router(cameras.router, prefix="/api/v1/cameras", tags=["cameras"])
app.include_router(snapshots.router, prefix="/api/v1")
# from app.routers import areas
# app.include_router(areas.router, prefix="/api/v1/areas", tags=["areas"])


@app.get("/health/")
async def health() -> dict[str, str]:
    return {"status": "ok"}
