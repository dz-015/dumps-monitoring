"""Prediction endpoint — real RT-DETR inference over ONNX Runtime."""

import io
import logging
from datetime import datetime

import anyio.to_thread
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.auth import get_current_user
from app.config import settings
from app.ml import ModelsUnavailableError
from app.ml.pipeline import get_pipeline
from app.schemas import PredictionBox, PredictResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/predict", tags=["predict"])


@router.post("", response_model=PredictResponse)
async def predict(
    file: UploadFile = File(...),
    # Optional: without a camera we cannot pick the right ROI, so the
    # prediction is returned unfiltered. The hourly scheduler always passes it.
    camera_key: str | None = Form(default=None),
    taken_at: datetime | None = Form(default=None),
    _=Depends(get_current_user),
):
    payload = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(payload) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image too large")

    try:
        image = Image.open(io.BytesIO(payload))
        image.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="Not a readable image") from None

    try:
        verdict = await anyio.to_thread.run_sync(
            lambda: get_pipeline().run(image, camera_key=camera_key, taken_at=taken_at)
        )
    except ModelsUnavailableError as exc:
        # The models are mounted, not baked into the image — a missing mount is
        # an operational problem, and 503 says so honestly.
        logger.error("inference unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="Model is not available") from exc

    return PredictResponse(
        detections=[
            PredictionBox(
                class_name=d.class_name,
                confidence=round(d.confidence, 4),
                x=round(d.x, 4),
                y=round(d.y, 4),
                w=round(d.w, 4),
                h=round(d.h, 4),
            )
            for d in verdict.detections
        ],
        has_overflow=verdict.has_overflow,
        has_contamination=verdict.has_contamination,
    )
