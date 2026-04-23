"""
Mock prediction endpoint.
Will be replaced with real YOLOv8m inference once ML model is trained.
"""
import random
from fastapi import APIRouter, Depends, UploadFile, File
from backend.app.schemas import PredictResponse, PredictionBox
from backend.app.auth import get_current_user

router = APIRouter(prefix="/api/predict", tags=["predict"])


@router.post("", response_model=PredictResponse)
async def predict(
    file: UploadFile = File(...),
    _=Depends(get_current_user),
):
    # ── MOCK: return random detections ──
    classes_ok = ["metal_ok", "plastic_ok", "euro_ok"]
    classes_overflow = ["metal_overflow", "plastic_overflow", "euro_overflow"]

    detections = []
    num_bins = random.randint(2, 5)
    for i in range(num_bins):
        is_overflow = random.random() < 0.15
        cls = random.choice(classes_overflow if is_overflow else classes_ok)
        detections.append(PredictionBox(
            class_name=cls,
            confidence=round(random.uniform(0.7, 0.99), 2),
            x=round(random.uniform(0.05, 0.6), 3),
            y=round(random.uniform(0.2, 0.7), 3),
            w=round(random.uniform(0.08, 0.2), 3),
            h=round(random.uniform(0.15, 0.35), 3),
        ))

    # 10% chance of ground trash
    if random.random() < 0.10:
        detections.append(PredictionBox(
            class_name="ground_trash",
            confidence=round(random.uniform(0.6, 0.95), 2),
            x=round(random.uniform(0.0, 0.5), 3),
            y=round(random.uniform(0.5, 0.8), 3),
            w=round(random.uniform(0.2, 0.5), 3),
            h=round(random.uniform(0.1, 0.3), 3),
        ))

    has_overflow = any(d.class_name.endswith("_overflow") for d in detections)
    has_contamination = any(d.class_name == "ground_trash" for d in detections)

    return PredictResponse(
        detections=detections,
        has_overflow=has_overflow,
        has_contamination=has_contamination,
    )
