"""Замер прод-пайплайна на валидации: сколько голосов ансамбля и нужен ли ROI.

Настройки по умолчанию в backend/app/config.py должны опираться на измерение,
а не на догадку. Скрипт гоняет ТОТ ЖЕ код, что и бэкенд (app.ml), на val-сплите
фолда и печатает P/R/F1 по классам для каждой конфигурации.

Инференс всех моделей выполняется ОДИН раз и кэшируется, дальше варианты
(число голосов × ROI вкл/выкл) считаются на кэше — иначе шесть прогонов по
300 кадров на CPU заняли бы час.

Запуск:  backend/venv/bin/python ml/scripts/eval_pipeline.py
"""

from __future__ import annotations

import pickle
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.ml.detector import CLASS_NAMES, Detector, _iou  # noqa: E402
from app.ml.roi import RoiConfig, inside  # noqa: E402

FOLD = ROOT / "ml" / "data" / "folds_temporal" / "fold_0"
MODELS = ROOT / "ml" / "models" / "rtdetr_temporal_640"
ROI_CONFIG = ROOT / "ml" / "configs" / "cameras_roi_v2.json"
CACHE = Path("/tmp/eval_pipeline_cache.pkl")

CONF = 0.25
MATCH_IOU = 0.5
HEADLINE = "bin_overflow"


def parse_name(path: Path) -> tuple[str, datetime]:
    """cam1_2026-04-28_114734.jpg → ("1", datetime(...UTC))."""
    cam, date, time_ = path.stem.split("_")
    stamp = datetime.strptime(f"{date}_{time_}", "%Y-%m-%d_%H%M%S")
    return cam.removeprefix("cam"), stamp.replace(tzinfo=timezone.utc)


def load_gt(label_path: Path) -> np.ndarray:
    """YOLO-разметка → (N, 5): [cx, cy, w, h, class]."""
    if not label_path.is_file():
        return np.empty((0, 5), dtype=np.float32)
    rows = []
    for line in label_path.read_text().split("\n"):
        parts = line.split()
        if len(parts) == 5:
            cls, cx, cy, w, h = parts
            rows.append([float(cx), float(cy), float(w), float(h), int(cls)])
    return np.array(rows, dtype=np.float32) if rows else np.empty((0, 5), dtype=np.float32)


def build_cache(detector: Detector) -> dict:
    detector.load()
    images = sorted((FOLD / "images" / "val").glob("*.jpg"))
    cache: dict[str, dict] = {}
    for i, img_path in enumerate(images, 1):
        image = Image.open(img_path)
        tensor = Detector.preprocess(image)
        per_model = [detector._run_one(s, tensor) for s in detector._sessions]
        cam, when = parse_name(img_path)
        cache[img_path.name] = {
            "per_model": per_model,
            "gt": load_gt(FOLD / "labels" / "val" / f"{img_path.stem}.txt"),
            "cam": cam,
            "when": when,
            "size": image.size,
        }
        if i % 50 == 0:
            print(f"  прогнано {i}/{len(images)}", flush=True)
    return cache


def evaluate(cache: dict, detector: Detector, votes: int, use_roi: bool,
             roi: RoiConfig, single_model: bool) -> dict[str, tuple[float, float, float]]:
    detector._min_votes = votes
    tp: defaultdict[int, int] = defaultdict(int)
    fp: defaultdict[int, int] = defaultdict(int)
    fn: defaultdict[int, int] = defaultdict(int)

    for item in cache.values():
        per_model = item["per_model"][:1] if single_model else item["per_model"]
        pred = per_model[0] if len(per_model) == 1 else detector._fuse(per_model)

        if use_roi and roi.has(item["cam"]):
            rects = roi.rects_at(item["cam"], item["when"])
            if rects:
                w, h = item["size"]
                pred = np.array([p for p in pred if inside(rects, p[0], p[1], w, h)]) \
                    if len(pred) else pred
                if len(pred) == 0:
                    pred = np.empty((0, 6), dtype=np.float32)

        gt = item["gt"]
        matched: set[int] = set()
        for p in sorted(pred, key=lambda r: -r[4]) if len(pred) else []:
            best, best_iou = -1, 0.0
            for gi, g in enumerate(gt):
                if gi in matched or int(g[4]) != int(p[5]):
                    continue
                score = _iou(p, g)
                if score > best_iou:
                    best, best_iou = gi, score
            if best_iou >= MATCH_IOU:
                matched.add(best)
                tp[int(p[5])] += 1
            else:
                fp[int(p[5])] += 1
        for gi, g in enumerate(gt):
            if gi not in matched:
                fn[int(g[4])] += 1

    out = {}
    for cls_id, name in CLASS_NAMES.items():
        precision = tp[cls_id] / (tp[cls_id] + fp[cls_id]) if tp[cls_id] + fp[cls_id] else 0.0
        recall = tp[cls_id] / (tp[cls_id] + fn[cls_id]) if tp[cls_id] + fn[cls_id] else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        out[name] = (precision, recall, f1)
    return out


def main() -> int:
    detector = Detector(MODELS, conf_threshold=CONF, min_votes=2)
    roi = RoiConfig.load(ROI_CONFIG)

    if CACHE.is_file():
        print(f"кэш: {CACHE}")
        cache = pickle.loads(CACHE.read_bytes())
        detector.load()
    else:
        print("прогоняю модели по val-сплиту (один раз)…")
        cache = build_cache(detector)
        CACHE.write_bytes(pickle.dumps(cache))

    print(f"\nкадров: {len(cache)} | порог {CONF} | матчинг IoU {MATCH_IOU}\n")
    header = f"{'конфигурация':28} " + " ".join(f"{n:>22}" for n in CLASS_NAMES.values())
    print(header)
    print("-" * len(header))

    configs = [
        ("один сид, без ROI", 1, False, True),
        ("один сид, с ROI", 1, True, True),
        ("ансамбль 2/3, без ROI", 2, False, False),
        ("ансамбль 2/3, с ROI", 2, True, False),
        ("ансамбль 3/3, с ROI", 3, True, False),
    ]
    results = {}
    for label, votes, use_roi, single in configs:
        scores = evaluate(cache, detector, votes, use_roi, roi, single)
        results[label] = scores
        cells = " ".join(
            f"  P{p:.3f} R{r:.3f} F{f:.3f}" for p, r, f in scores.values()
        )
        print(f"{label:28} {cells}")

    best = max(results.items(), key=lambda kv: kv[1][HEADLINE][2])
    print(f"\nлучшая по {HEADLINE} F1: {best[0]} → {best[1][HEADLINE][2]:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
