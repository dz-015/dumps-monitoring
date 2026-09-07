"""The whole inference path in one place, plus the process-wide singleton.

Loading three ONNX models costs ~1s and ~400 MB, so it happens once per process
and lazily — importing the app must stay cheap for the tests and for `alembic`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from app.config import settings
from app.ml.detector import Detection, Detector
from app.ml.roi import RoiConfig, inside


@dataclass(frozen=True)
class Verdict:
    detections: list[Detection]
    has_overflow: bool
    has_contamination: bool
    # Detections dropped by the ROI filter — useful for debugging a camera
    # whose ROI was drawn badly, and for the "why did it miss it" question.
    dropped_by_roi: int


class Pipeline:
    def __init__(self, detector: Detector, roi: RoiConfig | None):
        self._detector = detector
        self._roi = roi

    def run(
        self,
        image: Image.Image,
        camera_key: str | int | None = None,
        taken_at: datetime | None = None,
    ) -> Verdict:
        detections = self._detector.predict(image)
        dropped = 0

        # The ROI is optional: a camera without a drawn zone still works, it
        # just keeps the predictions the zone would have filtered out.
        if self._roi is not None and camera_key is not None and self._roi.has(camera_key):
            when = taken_at or datetime.now(timezone.utc)
            rects = self._roi.rects_at(camera_key, when)
            if rects:
                kept = [
                    d for d in detections
                    if inside(rects, d.x, d.y, image.width, image.height)
                ]
                dropped = len(detections) - len(kept)
                detections = kept

        return Verdict(
            detections=detections,
            has_overflow=any(d.class_name == "bin_overflow" for d in detections),
            has_contamination=any(d.class_name == "ground_trash" for d in detections),
            dropped_by_roi=dropped,
        )


_pipeline: Pipeline | None = None


def get_pipeline() -> Pipeline:
    global _pipeline
    if _pipeline is None:
        roi_path = Path(settings.ML_ROI_CONFIG)
        _pipeline = Pipeline(
            detector=Detector(
                model_dir=settings.ML_MODEL_DIR,
                conf_threshold=settings.ML_CONF_THRESHOLD,
                min_votes=settings.ML_MIN_VOTES,
            ),
            roi=RoiConfig.load(roi_path) if roi_path.is_file() else None,
        )
    return _pipeline
