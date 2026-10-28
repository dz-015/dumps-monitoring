"""Test SAHI (Slicing Aided Hyper Inference) on cam_2 validation set.

Compares:
- Standard inference (full frame)
- SAHI inference (overlapping slices, merged predictions)

For each: compute per-image P/R/F1 against ground truth, report mean LOSO numbers.

Hypothesis (cowork research): SAHI helps multi-scale + small objects.
cam_2 has 3% bboxes <32px and 2.9× scale variance — should benefit.

Usage:
    python sahi_inference_test.py \\
        --weights runs/detect/runs/level1/level1_baseline/fold_1_seed_1/weights/best.pt \\
        --fold-dir data/folds/fold_1 \\
        --slice-size 320 \\
        --overlap 0.2 \\
        --out-json runs/analysis/sahi_cam2.json
"""

from __future__ import annotations

import json
from pathlib import Path

import click


CLASS_NAMES = {0: "bin_ok", 1: "bin_overflow", 2: "ground_trash"}


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


def compute_p_r(preds, gts, iou_threshold=0.5):
    preds_sorted = sorted(preds, key=lambda p: -p[5])
    gt_matched = [False] * len(gts)
    tp = 0
    for p in preds_sorted:
        px1, py1, px2, py2, pc, _ = p
        best_iou, best_j = 0.0, -1
        for j, g in enumerate(gts):
            if gt_matched[j] or g[4] != pc:
                continue
            iou = box_iou((px1, py1, px2, py2), g[:4])
            if iou > best_iou:
                best_iou, best_j = iou, j
        if best_j >= 0 and best_iou >= iou_threshold:
            gt_matched[best_j] = True
            tp += 1
    fp = len(preds_sorted) - tp
    fn = sum(1 for m in gt_matched if not m)
    return tp, fp, fn


@click.command()
@click.option("--weights", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--fold-dir", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--slice-size", type=int, default=320)
@click.option("--overlap", type=float, default=0.2)
@click.option("--conf", type=float, default=0.25)
@click.option("--iou-threshold", type=float, default=0.5)
@click.option("--device", default="0")
@click.option("--out-json", type=click.Path(path_type=Path), required=True)
@click.option("--max-images", type=int, default=None, help="Limit for quick test")
def main(weights, fold_dir, slice_size, overlap, conf, iou_threshold, device, out_json, max_images):
    from PIL import Image
    from sahi import AutoDetectionModel
    from sahi.predict import get_prediction, get_sliced_prediction
    from ultralytics import YOLO

    click.echo(f"Loading SAHI model: {weights}")
    sahi_model = AutoDetectionModel.from_pretrained(
        model_type="ultralytics",
        model_path=str(weights),
        confidence_threshold=conf,
        device=device if device != "cpu" else "cpu",
    )

    standard_model = YOLO(str(weights))

    val_images = sorted((fold_dir / "images" / "val").glob("*.jpg"))
    if max_images:
        val_images = val_images[:max_images]
    val_labels_dir = fold_dir / "labels" / "val"

    click.echo(f"Running on {len(val_images)} val images ...")

    std_tp = std_fp = std_fn = 0
    sahi_tp = sahi_fp = sahi_fn = 0
    n_done = 0

    for img_path in val_images:
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
                cx, cy, w_n, h_n = map(float, parts[1:5])
                x1 = (cx - w_n / 2) * W
                y1 = (cy - h_n / 2) * H
                x2 = (cx + w_n / 2) * W
                y2 = (cy + h_n / 2) * H
                gts.append((x1, y1, x2, y2, cls))

        # Standard inference
        std_results = standard_model.predict(
            source=str(img_path), device=device, verbose=False, save=False, conf=conf, iou=0.7
        )
        std_preds = []
        r = std_results[0]
        if r.boxes is not None and len(r.boxes) > 0:
            xyxy = r.boxes.xyxy.cpu().numpy()
            cls = r.boxes.cls.cpu().numpy().astype(int)
            conf_arr = r.boxes.conf.cpu().numpy()
            for i in range(len(xyxy)):
                std_preds.append(
                    (float(xyxy[i, 0]), float(xyxy[i, 1]),
                     float(xyxy[i, 2]), float(xyxy[i, 3]),
                     int(cls[i]), float(conf_arr[i]))
                )

        # SAHI inference
        sahi_result = get_sliced_prediction(
            str(img_path),
            sahi_model,
            slice_height=slice_size,
            slice_width=slice_size,
            overlap_height_ratio=overlap,
            overlap_width_ratio=overlap,
        )
        sahi_preds = []
        for op in sahi_result.object_prediction_list:
            bbox = op.bbox
            sahi_preds.append(
                (bbox.minx, bbox.miny, bbox.maxx, bbox.maxy,
                 op.category.id, op.score.value)
            )

        # Compute
        s_tp, s_fp, s_fn = compute_p_r(std_preds, gts, iou_threshold)
        a_tp, a_fp, a_fn = compute_p_r(sahi_preds, gts, iou_threshold)
        std_tp += s_tp; std_fp += s_fp; std_fn += s_fn
        sahi_tp += a_tp; sahi_fp += a_fp; sahi_fn += a_fn

        n_done += 1
        if n_done % 25 == 0:
            click.echo(
                f"  {n_done}/{len(val_images)}: std P/R/F1 from current totals "
                f"std=({std_tp}/{std_fp}/{std_fn}) sahi=({sahi_tp}/{sahi_fp}/{sahi_fn})"
            )

    def pr(tp, fp, fn):
        p = tp / (tp + fp) if (tp + fp) > 0 else 0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
        return p, r, f1

    std_p, std_r, std_f1 = pr(std_tp, std_fp, std_fn)
    sahi_p, sahi_r, sahi_f1 = pr(sahi_tp, sahi_fp, sahi_fn)

    summary = {
        "weights": str(weights),
        "fold": str(fold_dir),
        "n_images": len(val_images),
        "slice_size": slice_size,
        "overlap": overlap,
        "conf": conf,
        "standard": {"tp": std_tp, "fp": std_fp, "fn": std_fn,
                     "P": std_p, "R": std_r, "F1": std_f1},
        "sahi": {"tp": sahi_tp, "fp": sahi_fp, "fn": sahi_fn,
                 "P": sahi_p, "R": sahi_r, "F1": sahi_f1},
        "delta": {"P": sahi_p - std_p, "R": sahi_r - std_r, "F1": sahi_f1 - std_f1},
    }

    click.echo(f"\n=== SAHI vs Standard ({len(val_images)} images, slice={slice_size}, overlap={overlap}) ===")
    click.echo(f"Standard: P={std_p:.4f}, R={std_r:.4f}, F1={std_f1:.4f}  TP/FP/FN={std_tp}/{std_fp}/{std_fn}")
    click.echo(f"SAHI:     P={sahi_p:.4f}, R={sahi_r:.4f}, F1={sahi_f1:.4f}  TP/FP/FN={sahi_tp}/{sahi_fp}/{sahi_fn}")
    click.echo(f"Δ:        P={sahi_p - std_p:+.4f}, R={sahi_r - std_r:+.4f}, F1={sahi_f1 - std_f1:+.4f}")

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2))
    click.echo(f"\nSaved: {out_json}")


if __name__ == "__main__":
    main()
