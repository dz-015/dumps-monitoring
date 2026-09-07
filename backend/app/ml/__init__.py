"""Inference pipeline: preprocess → RT-DETR (ONNX) → ROI filter → verdict.

Deliberately light: importing the package must not pull in app.config, so that
offline tools (evaluation scripts, notebooks) can use the detector without the
app's settings — and so a broken .env never takes the model down with it.
Import `app.ml.pipeline` explicitly when you want the configured singleton.
"""

from app.ml.detector import CLASS_NAMES, Detection, Detector, ModelsUnavailable
from app.ml.roi import RoiConfig, inside

__all__ = [
    "CLASS_NAMES",
    "Detection",
    "Detector",
    "ModelsUnavailable",
    "RoiConfig",
    "inside",
]
