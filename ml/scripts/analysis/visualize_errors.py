"""Visualize model errors on a fold: overlay predictions (red) + ground truth (green).

For each val image, compute per-image P/R, sort by worst-recall (most missed GT)
and worst-precision (most hallucinated). Save top-N visualisations of each.

Usage:
    python visualize_errors.py \\
        --weights runs/detect/runs/rtdetr/rtdetr_baseline/fold_1_seed_1/weights/best.pt \\
        --fold-dir data/folds/fold_1 \\
        --out-dir runs/analysis/cam2_errors \\
        --top-n 20
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import click


CLASS_COLORS = {
    0: (50, 200, 50),    # bin_ok — green
    1: (50, 50, 200),    # bin_overflow — red-blue
    2: (200, 150, 50),   # ground_trash — orange
}
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


@click.command()
@click.option("--weights", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--fold-dir", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--out-dir", type=click.Path(path_type=Path), required=True)
@click.option("--top-n", type=int, default=20, help="N worst frames per error type")
@click.option("--conf", type=float, default=0.25)
@click.option("--iou-thresh", type=float, default=0.5)
@click.option("--device", default="0")
def main(weights, fold_dir, out_dir, top_n, conf, iou_thresh, device):
    os.environ.setdefault("WANDB_MODE", "disabled")
    import cv2
    import numpy as np
    from ultralytics import YOLO

    out_dir = Path(out_dir)
    (out_dir / "missed_gt").mkdir(parents=True, exist_ok=True)
    (out_dir / "hallucinated").mkdir(parents=True, exist_ok=True)
    (out_dir / "good_examples").mkdir(parents=True, exist_ok=True)

    val_images = sorted((fold_dir / "images" / "val").glob("*.jpg"))
    val_labels_dir = fold_dir / "labels" / "val"

    click.echo(f"Loading {weights}")
    model = YOLO(str(weights))

    per_image = []
    click.echo(f"Inference on {len(val_images)} val images ...")
    for img_path in val_images:
        results = model.predict(
            source=str(img_path),
            device=device,
            verbose=False,
            save=False,
            conf=conf,
            iou=0.7,
        )
        r = results[0]
        H, W = r.orig_shape

        preds = []
        if r.boxes is not None and len(r.boxes) > 0:
            xyxy = r.boxes.xyxy.cpu().numpy()
            cls = r.boxes.cls.cpu().numpy().astype(int)
            conf_arr = r.boxes.conf.cpu().numpy()
            for i in range(len(xyxy)):
                preds.append(
                    (float(xyxy[i, 0]), float(xyxy[i, 1]),
                     float(xyxy[i, 2]), float(xyxy[i, 3]),
                     int(cls[i]), float(conf_arr[i]))
                )

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

        # Match greedy by descending conf
        preds_sorted = sorted(preds, key=lambda p: -p[5])
        gt_matched = [False] * len(gts)
        pred_matched = [False] * len(preds_sorted)
        for i, p in enumerate(preds_sorted):
            px1, py1, px2, py2, pc, _ = p
            best_iou, best_j = 0.0, -1
            for j, g in enumerate(gts):
                if gt_matched[j] or g[4] != pc:
                    continue
                iou = box_iou((px1, py1, px2, py2), g[:4])
                if iou > best_iou:
                    best_iou, best_j = iou, j
            if best_j >= 0 and best_iou >= iou_thresh:
                gt_matched[best_j] = True
                pred_matched[i] = True

        tp = sum(pred_matched)
        fp = len(preds_sorted) - tp
        fn = sum(1 for m in gt_matched if not m)
        p_img = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r_img = tp / (tp + fn) if (tp + fn) > 0 else 0.0

        per_image.append({
            "path": str(img_path),
            "stem": img_path.stem,
            "preds": preds_sorted,
            "gts": gts,
            "gt_matched": gt_matched,
            "pred_matched": pred_matched,
            "tp": tp, "fp": fp, "fn": fn,
            "p": p_img, "r": r_img,
        })

    click.echo("Rendering visualisations ...")
    # Worst recall (most missed GT)
    worst_recall = sorted(per_image, key=lambda d: (d["r"], -d["fn"]))[:top_n]
    # Worst precision (most hallucinations)
    worst_precision = sorted(per_image, key=lambda d: (d["p"], -d["fp"]))[:top_n]
    # Good examples (high P and R)
    good = sorted(per_image, key=lambda d: -(d["p"] + d["r"]))[:5]

    def draw(data, output_path):
        img = cv2.imread(data["path"])
        # GT bboxes: thick green/colored
        for j, g in enumerate(data["gts"]):
            x1, y1, x2, y2, cls = g
            color = CLASS_COLORS[cls]
            thickness = 3 if data["gt_matched"][j] else 6  # missed = thicker
            style = "" if data["gt_matched"][j] else " MISSED"
            cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), color, thickness)
            cv2.putText(img, f"GT:{CLASS_NAMES[cls]}{style}",
                        (int(x1), max(int(y1) - 6, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
        # Predictions: dashed-style (just thinner line, different color tone)
        for i, p in enumerate(data["preds"]):
            x1, y1, x2, y2, cls, conf_v = p
            color = (220, 50, 220) if not data["pred_matched"][i] else (50, 220, 220)  # FP=magenta, TP=cyan
            label_pref = "TP" if data["pred_matched"][i] else "FP"
            cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
            cv2.putText(img, f"{label_pref}:{CLASS_NAMES[cls]} {conf_v:.2f}",
                        (int(x1), int(y2) + 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        # Top stats
        cv2.putText(img,
                    f"{data['stem']}  TP={data['tp']} FP={data['fp']} FN={data['fn']}  P={data['p']:.2f} R={data['r']:.2f}",
                    (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.imwrite(str(output_path), img)

    for idx, d in enumerate(worst_recall):
        draw(d, out_dir / "missed_gt" / f"{idx:02d}_{d['stem']}_R{d['r']:.2f}_FN{d['fn']}.jpg")
    for idx, d in enumerate(worst_precision):
        draw(d, out_dir / "hallucinated" / f"{idx:02d}_{d['stem']}_P{d['p']:.2f}_FP{d['fp']}.jpg")
    for idx, d in enumerate(good):
        draw(d, out_dir / "good_examples" / f"{idx:02d}_{d['stem']}_P{d['p']:.2f}_R{d['r']:.2f}.jpg")

    # Save aggregate stats
    summary = {
        "n_val_images": len(val_images),
        "mean_p": sum(d["p"] for d in per_image) / len(per_image),
        "mean_r": sum(d["r"] for d in per_image) / len(per_image),
        "frames_zero_recall": sum(1 for d in per_image if d["r"] == 0 and len(d["gts"]) > 0),
        "frames_with_hallucinations": sum(1 for d in per_image if d["fp"] > 0),
        "total_gt": sum(len(d["gts"]) for d in per_image),
        "total_missed": sum(d["fn"] for d in per_image),
        "total_hallucinated": sum(d["fp"] for d in per_image),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    click.echo(f"\nSaved {top_n} worst-recall + {top_n} worst-precision + 5 good to {out_dir}")
    click.echo(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
