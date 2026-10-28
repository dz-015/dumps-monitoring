"""Тесты инференс-пайплайна: ансамблирование, ROI, вердикт, HTTP-контракт.

Всё, кроме последнего интеграционного теста, работает без onnxruntime и без
файлов моделей — Detector подменяется стабом. Контракт модели (вход/выход)
зафиксирован в docstring app/ml/detector.py и проверен эмпирически 31.07.2026.
"""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.ml.detector import CLASS_NAMES, Detection, Detector, ModelsUnavailableError, _iou
from app.ml.pipeline import Pipeline, Verdict
from app.ml.roi import RoiConfig, inside
from tests.conftest import auth_headers, make_org, make_user


def det(cx, cy, w, h, conf, cls) -> np.ndarray:
    return np.array([cx, cy, w, h, conf, cls], dtype=np.float32)


# ── _iou ─────────────────────────────────────────────────────────────────

def test_iou_identical_boxes():
    a = det(0.5, 0.5, 0.2, 0.2, 0.9, 0)
    assert _iou(a, a) == pytest.approx(1.0)


def test_iou_disjoint_boxes():
    assert _iou(det(0.2, 0.2, 0.1, 0.1, 0.9, 0), det(0.8, 0.8, 0.1, 0.1, 0.9, 0)) == 0.0


def test_iou_half_shift():
    # Сдвиг на половину ширины: пересечение 0.5·площади, объединение 1.5·площади.
    a = det(0.5, 0.5, 0.2, 0.2, 0.9, 0)
    b = det(0.6, 0.5, 0.2, 0.2, 0.9, 0)
    assert _iou(a, b) == pytest.approx(1 / 3, abs=1e-6)


# ── preprocess ───────────────────────────────────────────────────────────

def test_preprocess_shape_and_range():
    image = Image.new("RGB", (1920, 1080), color=(255, 128, 0))
    tensor = Detector.preprocess(image)
    assert tensor.shape == (1, 3, 640, 640)
    assert tensor.dtype == np.float32
    assert tensor[0, 0].max() == pytest.approx(1.0)  # R=255 → 1.0
    assert tensor[0, 2].max() == pytest.approx(0.0)  # B=0 → 0.0 (порядок RGB)


def test_preprocess_accepts_grayscale():
    tensor = Detector.preprocess(Image.new("L", (640, 480), color=128))
    assert tensor.shape == (1, 3, 640, 640)


# ── _fuse (ансамблирование голосованием) ─────────────────────────────────

def make_detector(min_votes: int = 2) -> Detector:
    return Detector("/nonexistent", conf_threshold=0.25, min_votes=min_votes)


def test_fuse_keeps_agreement_of_two():
    d = make_detector(min_votes=2)
    a = det(0.5, 0.5, 0.2, 0.2, 0.9, 1)
    b = det(0.51, 0.5, 0.2, 0.2, 0.8, 1)
    fused = d._fuse([np.stack([a]), np.stack([b]), np.empty((0, 6), np.float32)])
    assert len(fused) == 1
    # Бокс — среднее кластера.
    assert fused[0][0] == pytest.approx(0.505, abs=1e-6)
    assert fused[0][4] == pytest.approx(0.85, abs=1e-6)


def test_fuse_drops_single_vote():
    d = make_detector(min_votes=2)
    lone = np.stack([det(0.5, 0.5, 0.2, 0.2, 0.99, 1)])
    empty = np.empty((0, 6), np.float32)
    assert len(d._fuse([lone, empty, empty])) == 0


def test_fuse_min_votes_one_keeps_everything():
    d = make_detector(min_votes=1)
    lone = np.stack([det(0.5, 0.5, 0.2, 0.2, 0.99, 1)])
    empty = np.empty((0, 6), np.float32)
    assert len(d._fuse([lone, empty, empty])) == 1


def test_fuse_does_not_cluster_different_classes():
    d = make_detector(min_votes=2)
    a = np.stack([det(0.5, 0.5, 0.2, 0.2, 0.9, 0)])
    b = np.stack([det(0.5, 0.5, 0.2, 0.2, 0.8, 1)])  # тот же бокс, другой класс
    assert len(d._fuse([a, b, np.empty((0, 6), np.float32)])) == 0


def test_fuse_single_model_is_passthrough():
    d = make_detector(min_votes=2)
    dets = np.stack([det(0.5, 0.5, 0.2, 0.2, 0.9, 0)])
    assert len(d._fuse([dets])) == 1


def test_fuse_three_way_agreement_survives_three_votes():
    d = make_detector(min_votes=3)
    rows = [det(0.5 + i * 0.005, 0.5, 0.2, 0.2, 0.9 - i * 0.1, 2) for i in range(3)]
    fused = d._fuse([np.stack([r]) for r in rows])
    assert len(fused) == 1
    assert int(fused[0][5]) == 2


def test_load_missing_dir_raises_models_unavailable():
    with pytest.raises(ModelsUnavailableError):
        make_detector().load()


# ── RoiConfig ────────────────────────────────────────────────────────────

@pytest.fixture
def roi_file(tmp_path: Path) -> Path:
    cfg = {
        "_комментарий": "служебный ключ, не камера",
        "7": {"rects": [[297, 211, 1078, 586]]},
        "2": {
            "periods": [
                {"until": "2026-03-04T15:34:00Z", "rects": [[464, 354, 1874, 728]]},
                {"until": "2026-03-27T09:34:00Z", "rects": [[545, 104, 1411, 746]]},
                {"until": None, "rects": [[557, 96, 1441, 421]]},
            ]
        },
    }
    path = tmp_path / "roi.json"
    path.write_text(json.dumps(cfg))
    return path


def test_roi_load_skips_underscore_keys(roi_file):
    roi = RoiConfig.load(roi_file)
    assert roi.has("7") and roi.has(7) and roi.has("2")
    assert not roi.has("_комментарий")
    assert not roi.has("99")


def test_roi_rects_at_picks_period_by_timestamp(roi_file):
    roi = RoiConfig.load(roi_file)
    early = datetime(2026, 2, 1, tzinfo=UTC)
    mid = datetime(2026, 3, 10, tzinfo=UTC)
    late = datetime(2026, 7, 1, tzinfo=UTC)
    assert roi.rects_at("2", early) == ((464, 354, 1874, 728),)
    assert roi.rects_at("2", mid) == ((545, 104, 1411, 746),)
    assert roi.rects_at("2", late) == ((557, 96, 1441, 421),)


def test_roi_naive_datetime_treated_as_utc(roi_file):
    roi = RoiConfig.load(roi_file)
    assert roi.rects_at("2", datetime(2026, 7, 1)) == ((557, 96, 1441, 421),)


def test_inside_uses_box_centre():
    rects = ((100, 100, 200, 200),)
    # Центр (150, 150) в кадре 1000×1000 → внутри.
    assert inside(rects, 0.15, 0.15, 1000, 1000)
    # Центр за пределами, даже если края бокса пересекали бы ROI.
    assert not inside(rects, 0.5, 0.5, 1000, 1000)


# ── Pipeline ─────────────────────────────────────────────────────────────

class StubDetector:
    def __init__(self, detections: list[Detection]):
        self._detections = detections

    def predict(self, image):
        return self._detections


def bin_overflow_at(x: float, y: float) -> Detection:
    return Detection("bin_overflow", 0.9, x, y, 0.1, 0.1)


def test_pipeline_verdict_flags(roi_file):
    dets = [
        Detection("bin_ok", 0.9, 0.2, 0.2, 0.1, 0.1),
        Detection("ground_trash", 0.6, 0.8, 0.8, 0.2, 0.1),
    ]
    verdict = Pipeline(StubDetector(dets), roi=None).run(Image.new("RGB", (1920, 1080)))
    assert not verdict.has_overflow
    assert verdict.has_contamination
    assert verdict.dropped_by_roi == 0


def test_pipeline_roi_drops_outside_centre(roi_file):
    roi = RoiConfig.load(roi_file)
    image = Image.new("RGB", (1920, 1080))
    # cam_7 ROI = [297, 211, 1078, 586]. Внутри: (600/1920, 400/1080).
    inside_det = bin_overflow_at(600 / 1920, 400 / 1080)
    outside_det = bin_overflow_at(0.95, 0.95)
    verdict = Pipeline(StubDetector([inside_det, outside_det]), roi).run(
        image, camera_key="7", taken_at=datetime(2026, 7, 1, tzinfo=UTC)
    )
    assert verdict.detections == [inside_det]
    assert verdict.dropped_by_roi == 1
    assert verdict.has_overflow


def test_pipeline_without_camera_key_skips_roi(roi_file):
    roi = RoiConfig.load(roi_file)
    outside_det = bin_overflow_at(0.95, 0.95)
    verdict = Pipeline(StubDetector([outside_det]), roi).run(Image.new("RGB", (1920, 1080)))
    assert verdict.detections == [outside_det]
    assert verdict.dropped_by_roi == 0


def test_pipeline_unknown_camera_skips_roi(roi_file):
    roi = RoiConfig.load(roi_file)
    outside_det = bin_overflow_at(0.95, 0.95)
    verdict = Pipeline(StubDetector([outside_det]), roi).run(
        Image.new("RGB", (1920, 1080)), camera_key="99"
    )
    assert verdict.detections == [outside_det]


# ── HTTP-контракт /api/predict ───────────────────────────────────────────

def jpeg_bytes(size=(64, 64)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=(120, 130, 140)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def user_headers(db):
    org = make_org(db)
    return auth_headers(make_user(db, email="ml@test.io", org=org))


def stub_pipeline(monkeypatch, verdict=None, exc: Exception | None = None):
    class _Stub:
        def run(self, image, camera_key=None, taken_at=None):
            if exc is not None:
                raise exc
            return verdict

    import app.routers.predict as predict_module
    monkeypatch.setattr(predict_module, "get_pipeline", lambda: _Stub())


def test_predict_requires_auth(client):
    resp = client.post("/api/predict", files={"file": ("a.jpg", jpeg_bytes(), "image/jpeg")})
    assert resp.status_code == 401


def test_predict_rejects_non_image(client, user_headers):
    resp = client.post(
        "/api/predict",
        files={"file": ("a.jpg", b"definitely not a jpeg", "image/jpeg")},
        headers=user_headers,
    )
    assert resp.status_code == 400


def test_predict_rejects_oversized_upload(client, user_headers, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 1024)
    resp = client.post(
        "/api/predict",
        files={"file": ("a.jpg", b"x" * 2048, "image/jpeg")},
        headers=user_headers,
    )
    assert resp.status_code == 413


def test_predict_returns_detections(client, user_headers, monkeypatch):
    verdict = Verdict(
        detections=[Detection("bin_overflow", 0.87654, 0.5, 0.5, 0.2, 0.3)],
        has_overflow=True,
        has_contamination=False,
        dropped_by_roi=1,
    )
    stub_pipeline(monkeypatch, verdict=verdict)
    resp = client.post(
        "/api/predict",
        files={"file": ("a.jpg", jpeg_bytes(), "image/jpeg")},
        data={"camera_key": "7"},
        headers=user_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_overflow"] is True
    assert body["has_contamination"] is False
    assert body["detections"] == [
        {
            "class_name": "bin_overflow",
            "confidence": 0.8765,
            "x": 0.5, "y": 0.5, "w": 0.2, "h": 0.3,
        }
    ]


def test_predict_503_when_models_missing(client, user_headers, monkeypatch):
    stub_pipeline(monkeypatch, exc=ModelsUnavailableError("no models"))
    resp = client.post(
        "/api/predict",
        files={"file": ("a.jpg", jpeg_bytes(), "image/jpeg")},
        headers=user_headers,
    )
    assert resp.status_code == 503


# ── Интеграция с реальными моделями (пропускается без файлов) ────────────

MODELS_DIR = Path(__file__).resolve().parents[2] / "ml" / "models" / "rtdetr_temporal_640"


@pytest.mark.skipif(
    not any(MODELS_DIR.glob("*.onnx")) if MODELS_DIR.is_dir() else True,
    reason="ONNX-модели не установлены",
)
def test_real_models_run_and_return_contracted_classes():
    pytest.importorskip("onnxruntime")
    detector = Detector(MODELS_DIR, conf_threshold=0.25, min_votes=2)
    detections = detector.predict(Image.new("RGB", (1920, 1080), color=(90, 90, 90)))
    # На сером кадре ансамбль ничего уверенного не находит, но главное —
    # прогон трёх моделей не падает и классы (если есть) из контракта.
    assert all(d.class_name in CLASS_NAMES.values() for d in detections)
