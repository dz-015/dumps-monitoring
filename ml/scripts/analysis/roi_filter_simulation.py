"""Simulate post-inference ROI filtering: drop predictions outside ROI,
recompute P/R/F1, compare with baseline.

Supports both single-rect ROI ([x1,y1,x2,y2]) and multi-rect ROI
([[x1,y1,x2,y2], [x1,y1,x2,y2], ...]). Prediction is "inside" if its centre
lies inside ANY of the rectangles (union semantics).

Usage:
    python roi_filter_simulation.py \\
        --weights runs/detect/runs/level1_tuned/level1_tuned/fold_1_seed_1/weights/best.pt \\
        --fold-dir data/folds/fold_1 \\
        --camera 2 \\
        --target-class 1 \\
        --target-class-name bin_overflow
"""
from __future__ import annotations

import json
from pathlib import Path

import click


def load_roi(roi_config: Path, camera: str) -> list[tuple[int, int, int, int]]:
    """Returns list of (x1, y1, x2, y2) rectangles for the camera."""
    cfg = json.loads(roi_config.read_text())
    val = cfg.get(camera) or cfg.get(str(camera))
    if val is None:
        raise KeyError(f"No ROI for camera {camera}")
    if isinstance(val, list) and val and isinstance(val[0], (int, float)):
        return [tuple(val)]  # single rect
    return [tuple(r) for r in val]  # multi-rect


def inside_roi(bx1, by1, bx2, by2, rects) -> bool:
    cx, cy = (bx1 + bx2) / 2, (by1 + by2) / 2
    for rx1, ry1, rx2, ry2 in rects:
        if rx1 <= cx <= rx2 and ry1 <= cy <= ry2:
            return True
    return False


def box_iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    aarea = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    barea = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = aarea + barea - inter
    return inter / union if union > 0 else 0.0


def compute_metrics(matched_preds: list[tuple[float, bool]], total_gt: int) -> dict:
    """Compute P/R/F1 at default conf threshold from matched predictions."""
    tp = sum(1 for _, is_tp in matched_preds if is_tp)
    fp = len(matched_preds) - tp
    fn = max(0, total_gt - tp)
    p = tp / (tp + fp) if (tp + fp) > 0 else 0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
    return {"tp": tp, "fp": fp, "fn": fn, "P": p, "R": r, "F1": f1}


@click.command()
@click.option("--weights", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--fold-dir", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--camera", required=True, help="Camera id (matches keys in cameras_roi.json)")
@click.option("--roi-config", type=click.Path(path_type=Path, exists=True),
              default=Path("configs/cameras_roi.json"))
@click.option("--target-class", type=int, default=None,
              help="If set, only consider this class (e.g. 1 for bin_overflow)")
@click.option("--target-class-name", default="all")
@click.option("--conf", type=float, default=0.25)
@click.option("--iou-threshold", type=float, default=0.5)
@click.option("--device", default="0")
def main(weights, fold_dir, camera, roi_config, target_class, target_class_name,
         conf, iou_threshold, device):
    from PIL import Image
    from ultralytics import YOLO

    rects = load_roi(roi_config, camera)
    print(f"ROI for cam_{camera}: {len(rects)} rectangle(s) — {rects}")

    val_images_dir = fold_dir / "images" / "val"
    val_labels_dir = fold_dir / "labels" / "val"
    val_frames = sorted(val_images_dir.glob(f"cam{camera}_*.jpg"))
    print(f"Inferencing on {len(val_frames)} frames ...")

    model = YOLO(str(weights))

    matched_baseline = []   # (conf, is_tp) — all predictions
    matched_roi = []        # (conf, is_tp) — only inside-ROI predictions
    total_gt_baseline = 0
    total_gt_inside_roi = 0
    n_pred_inside = 0
    n_pred_outside = 0

    for img_path in val_frames:
        with Image.open(img_path) as im:
            W, H = im.size

        # Load GT
        gts = []
        lbl = val_labels_dir / (img_path.stem + ".txt")
        if lbl.exists() and lbl.stat().st_size > 0:
            for line in lbl.read_text().strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split()
                cls = int(parts[0])
                if target_class is not None and cls != target_class:
                    continue
                cx, cy, w_n, h_n = map(float, parts[1:5])
                x1 = (cx - w_n / 2) * W
                y1 = (cy - h_n / 2) * H
                x2 = (cx + w_n / 2) * W
                y2 = (cy + h_n / 2) * H
                gts.append((x1, y1, x2, y2, cls))

        gts_inside = [g for g in gts if inside_roi(*g[:4], rects)]
        total_gt_baseline += len(gts)
        total_gt_inside_roi += len(gts_inside)

        # Inference
        results = model.predict(source=str(img_path), device=device, verbose=False,
                                save=False, conf=conf, iou=0.7)
        r = results[0]
        if r.boxes is None or len(r.boxes) == 0:
            continue
        xyxy = r.boxes.xyxy.cpu().numpy()
        cls_arr = r.boxes.cls.cpu().numpy().astype(int)
        conf_arr = r.boxes.conf.cpu().numpy()

        all_preds = []
        for i in range(len(xyxy)):
            if target_class is not None and int(cls_arr[i]) != target_class:
                continue
            all_preds.append((float(xyxy[i, 0]), float(xyxy[i, 1]),
                              float(xyxy[i, 2]), float(xyxy[i, 3]),
                              int(cls_arr[i]), float(conf_arr[i])))

        # Greedy match all_preds to gts (full GT, baseline)
        all_preds.sort(key=lambda p: -p[5])
        gt_matched_baseline = [False] * len(gts)
        for p in all_preds:
            best_iou, best_j = 0.0, -1
            for j, g in enumerate(gts):
                if gt_matched_baseline[j]:
                    continue
                if target_class is None and g[4] != p[4]:
                    continue
                iou = box_iou(p[:4], g[:4])
                if iou > best_iou:
                    best_iou, best_j = iou, j
            is_tp = best_j >= 0 and best_iou >= iou_threshold
            if is_tp:
                gt_matched_baseline[best_j] = True
            matched_baseline.append((p[5], is_tp))

        # ROI-filtered: drop preds whose centre is outside any ROI rect
        roi_preds = [p for p in all_preds if inside_roi(*p[:4], rects)]
        n_pred_inside += len(roi_preds)
        n_pred_outside += len(all_preds) - len(roi_preds)

        # Match roi_preds to gts_inside
        gt_matched_roi = [False] * len(gts_inside)
        for p in roi_preds:
            best_iou, best_j = 0.0, -1
            for j, g in enumerate(gts_inside):
                if gt_matched_roi[j]:
                    continue
                if target_class is None and g[4] != p[4]:
                    continue
                iou = box_iou(p[:4], g[:4])
                if iou > best_iou:
                    best_iou, best_j = iou, j
            is_tp = best_j >= 0 and best_iou >= iou_threshold
            if is_tp:
                gt_matched_roi[best_j] = True
            matched_roi.append((p[5], is_tp))

    base = compute_metrics(matched_baseline, total_gt_baseline)
    roi = compute_metrics(matched_roi, total_gt_inside_roi)

    print(f"\n=== ROI filter simulation: cam_{camera}, class={target_class_name} ===")
    print(f"  Total GT bboxes:        {total_gt_baseline} ({total_gt_inside_roi} inside ROI)")
    print(f"  Predictions inside ROI: {n_pred_inside}")
    print(f"  Predictions outside ROI: {n_pred_outside} ({100*n_pred_outside/(n_pred_inside+n_pred_outside):.1f}%)")
    print()
    print(f"  Baseline (no filter):  P={base['P']:.3f}  R={base['R']:.3f}  F1={base['F1']:.3f}  TP/FP/FN={base['tp']}/{base['fp']}/{base['fn']}")
    print(f"  ROI-filtered:          P={roi['P']:.3f}  R={roi['R']:.3f}  F1={roi['F1']:.3f}  TP/FP/FN={roi['tp']}/{roi['fp']}/{roi['fn']}")
    print(f"  Δ:                     P{roi['P']-base['P']:+.3f}  R{roi['R']-base['R']:+.3f}  F1{roi['F1']-base['F1']:+.3f}")


if __name__ == "__main__":
    main()
