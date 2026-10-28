"""RT-DETR inference over ONNX Runtime.

Model contract (verified against the PyTorch checkpoint on 2026-07-31, do not
guess at it):

* input  ``1x3x640x640`` float32, RGB, ``/255``. A plain resize to 640x640 —
  **no letterbox, no padding, no mean/std normalisation**. Ultralytics does the
  same for RT-DETR, and our output matches its predictions to 4 decimals.
* output ``(1, 300, 6)`` = ``[cx, cy, w, h, confidence, class_id]`` where the
  box is normalised to the ORIGINAL frame (0..1), not to the 640px input. That
  is exactly the convention the API and the frontend overlay already use, so no
  coordinate conversion happens anywhere.
* no NMS — RT-DETR's Hungarian matching already de-duplicates. (Re-sweeping an
  IoU threshold on it measured as a no-op.)

Production runs an ensemble of three seeds (decision D-23): a detection is kept
only if at least `min_votes` of the models agree on it, which suppresses the
single-seed flicker. Point the loader at one file to fall back to a single model.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

INPUT_SIZE = 640
CLASS_NAMES = {0: "bin_ok", 1: "bin_overflow", 2: "ground_trash"}

# Two detections are "the same object seen by two models" above this IoU.
_VOTE_IOU = 0.5


@dataclass(frozen=True)
class Detection:
    class_name: str
    confidence: float
    # Centre and size, normalised to the original frame.
    x: float
    y: float
    w: float
    h: float


class ModelsUnavailableError(RuntimeError):
    """No ONNX file was found — the API should answer 503, not 500."""


class Detector:
    """Lazily-loaded ensemble of ONNX models."""

    def __init__(
        self,
        model_dir: str | Path,
        conf_threshold: float = 0.25,
        min_votes: int = 2,
    ):
        self._model_dir = Path(model_dir)
        self._conf = conf_threshold
        self._min_votes = min_votes
        self._sessions: list = []
        self._input_name: str = ""

    # ── loading ──────────────────────────────────────────────────────────
    def load(self) -> None:
        if self._sessions:
            return
        # Imported here so the rest of the app (and the tests) stay importable
        # on machines without onnxruntime installed.
        import onnxruntime as ort

        paths = sorted(self._model_dir.glob("*.onnx"))
        if not paths:
            raise ModelsUnavailableError(f"no .onnx files in {self._model_dir}")

        for path in paths:
            self._sessions.append(
                ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
            )
        self._input_name = self._sessions[0].get_inputs()[0].name
        logger.info(
            "loaded %d ONNX model(s) from %s: %s",
            len(paths), self._model_dir, ", ".join(p.name for p in paths),
        )

    @property
    def ready(self) -> bool:
        return bool(self._sessions)

    @property
    def model_count(self) -> int:
        return len(self._sessions)

    # ── inference ────────────────────────────────────────────────────────
    def predict(self, image: Image.Image) -> list[Detection]:
        self.load()
        tensor = self.preprocess(image)
        per_model = [self._run_one(session, tensor) for session in self._sessions]
        fused = self._fuse(per_model)
        return [
            Detection(
                class_name=CLASS_NAMES.get(int(row[5]), str(int(row[5]))),
                confidence=float(row[4]),
                x=float(row[0]), y=float(row[1]), w=float(row[2]), h=float(row[3]),
            )
            for row in fused
        ]

    @staticmethod
    def preprocess(image: Image.Image) -> np.ndarray:
        resized = image.convert("RGB").resize((INPUT_SIZE, INPUT_SIZE))
        array = np.asarray(resized, dtype=np.float32).transpose(2, 0, 1) / 255.0
        return array[None]

    def _run_one(self, session, tensor: np.ndarray) -> np.ndarray:
        out = session.run(None, {self._input_name: tensor})[0][0]
        return out[out[:, 4] >= self._conf]

    # ── ensembling ───────────────────────────────────────────────────────
    def _fuse(self, per_model: list[np.ndarray]) -> np.ndarray:
        """Keep detections that at least `min_votes` models agree on.

        Greedy: walk detections by descending confidence, and for each one
        collect the best-matching detection of the same class from every other
        model. The survivor is the average of its cluster, which also smooths
        the box coordinates.
        """
        if len(per_model) == 1:
            return per_model[0]

        indexed = [
            (float(row[4]), model_idx, row)
            for model_idx, dets in enumerate(per_model)
            for row in dets
        ]
        indexed.sort(key=lambda item: item[0], reverse=True)

        used: set[tuple[int, int]] = set()
        fused: list[np.ndarray] = []
        for order, (_, model_idx, row) in enumerate(indexed):
            if (model_idx, order) in used:
                continue
            cluster = [row]
            claimed = [(model_idx, order)]
            for other_order, (_, other_idx, other_row) in enumerate(indexed):
                if other_idx == model_idx or (other_idx, other_order) in used:
                    continue
                if any(other_idx == idx for idx, _ in claimed):
                    continue
                if other_row[5] != row[5] or _iou(row, other_row) < _VOTE_IOU:
                    continue
                cluster.append(other_row)
                claimed.append((other_idx, other_order))
            if len(cluster) >= self._min_votes:
                used.update(claimed)
                fused.append(np.mean(np.stack(cluster), axis=0))

        if not fused:
            return np.empty((0, 6), dtype=np.float32)
        result = np.stack(fused)
        # Averaging can shift the class id off an integer if a cluster ever
        # mixed classes; it cannot here (we only cluster same-class boxes), but
        # rounding keeps the contract explicit.
        result[:, 5] = np.round(result[:, 5])
        return result[np.argsort(-result[:, 4])]


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    ax1, ay1, ax2, ay2 = a[0] - a[2] / 2, a[1] - a[3] / 2, a[0] + a[2] / 2, a[1] + a[3] / 2
    bx1, by1, bx2, by2 = b[0] - b[2] / 2, b[1] - b[3] / 2, b[0] + b[2] / 2, b[1] + b[3] / 2
    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = inter_w * inter_h
    union = a[2] * a[3] + b[2] * b[3] - inter
    return float(inter / union) if union > 0 else 0.0
