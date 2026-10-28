"""PR-curve threshold tuning to find conf_threshold satisfying operational target.

Operational target: Recall(bin_overflow) >= 0.70 at Precision(bin_overflow) >= 0.70.
Our LOSO mean is currently R=0.62 at default threshold 0.25. We sweep threshold
on the matched predictions to find the curve point closest to target.

For each fold, we:
- Run inference at conf=0.001 (capture all predictions)
- Match each prediction to GT bbox by IoU>=0.5
- Sort predictions by confidence DESC
- For each threshold = sorted_confidence, compute P and R cumulatively
- Find threshold that maximises (R - max(0, 0.70 - R)) * (P - max(0, 0.70 - P))
- Also find threshold where R == 0.70 exactly, report P at that point

Usage:
    python pr_curve_tuning.py \\
        --weights-dir runs/detect/runs/rtdetr/rtdetr_baseline \\
        --folds-dir data/folds \\
        --target-class 1 \\
        --target-class-name bin_overflow \\
        --out-json runs/analysis/pr_curve_rtdetr.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import click


RUN_DIR_RE = re.compile(r"fold_(\d+)_seed_(\d+)$")


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


def collect_predictions(model, fold_dir, target_class, conf, device):
    """Returns list of (confidence, is_TP, image_stem) and total positive GT count."""
    from PIL import Image

    val_images = sorted((fold_dir / "images" / "val").glob("*.jpg"))
    val_labels_dir = fold_dir / "labels" / "val"
    matched_preds = []
    total_gt = 0

    for img_path in val_images:
        with Image.open(img_path) as im:
            W, H = im.size

        gts = []
        lbl = val_labels_dir / (img_path.stem + ".txt")
        if lbl.exists() and lbl.stat().st_size > 0:
            for line in lbl.read_text().strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split()
                cls = int(parts[0])
                if cls != target_class:
                    continue
                cx, cy, w_n, h_n = map(float, parts[1:5])
                x1 = (cx - w_n / 2) * W
                y1 = (cy - h_n / 2) * H
                x2 = (cx + w_n / 2) * W
                y2 = (cy + h_n / 2) * H
                gts.append((x1, y1, x2, y2))
        total_gt += len(gts)

        preds_data = []
        results = model.predict(
            source=str(img_path), device=device, verbose=False, save=False, conf=conf, iou=0.7
        )
        r = results[0]
        if r.boxes is not None and len(r.boxes) > 0:
            xyxy = r.boxes.xyxy.cpu().numpy()
            cls = r.boxes.cls.cpu().numpy().astype(int)
            conf_arr = r.boxes.conf.cpu().numpy()
            for i in range(len(xyxy)):
                if int(cls[i]) != target_class:
                    continue
                preds_data.append(
                    (float(xyxy[i, 0]), float(xyxy[i, 1]),
                     float(xyxy[i, 2]), float(xyxy[i, 3]),
                     float(conf_arr[i]))
                )

        # Match greedy by confidence
        preds_sorted = sorted(preds_data, key=lambda p: -p[4])
        gt_matched = [False] * len(gts)
        for p in preds_sorted:
            px1, py1, px2, py2, pconf = p
            best_iou, best_j = 0.0, -1
            for j, g in enumerate(gts):
                if gt_matched[j]:
                    continue
                iou = box_iou((px1, py1, px2, py2), g)
                if iou > best_iou:
                    best_iou, best_j = iou, j
            is_tp = best_j >= 0 and best_iou >= 0.5
            if is_tp:
                gt_matched[best_j] = True
            matched_preds.append((pconf, is_tp))

    return matched_preds, total_gt


def compute_pr_curve(matched_preds, total_gt):
    """Returns sorted list of (threshold, P, R)."""
    sorted_preds = sorted(matched_preds, key=lambda x: -x[0])
    tp = fp = 0
    curve = []
    for conf, is_tp in sorted_preds:
        if is_tp:
            tp += 1
        else:
            fp += 1
        p = tp / (tp + fp) if (tp + fp) > 0 else 0
        r = tp / total_gt if total_gt > 0 else 0
        curve.append((conf, p, r))
    return curve


def find_target_threshold(curve, target_r=0.70, target_p=0.70):
    """Pick threshold closest to satisfying R>=target_r and P>=target_p.

    Strategy: find point where R first crosses target_r (smallest threshold
    achieving R>=target_r), then report P there. Also report point where P
    closest to target_p.
    """
    if not curve:
        return None

    # Lowest threshold (highest recall) achieving target R
    point_r_target = None
    for conf, p, r in curve:
        if r >= target_r:
            point_r_target = (conf, p, r)
            # don't break — keep last (lowest conf with R >= target)
    # Actually we want the FIRST point (highest conf) achieving R >= target
    for conf, p, r in curve:
        if r >= target_r:
            point_r_target = (conf, p, r)
            break

    # Point with highest F1
    best_f1 = -1
    best_f1_point = None
    for conf, p, r in curve:
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
        if f1 > best_f1:
            best_f1, best_f1_point = f1, (conf, p, r)

    return {
        "r_target_point": point_r_target,
        "best_f1_point": best_f1_point,
        "best_f1": best_f1,
    }


@click.command()
@click.option("--weights-dir", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--folds-dir", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--target-class", type=int, default=1)
@click.option("--target-class-name", default="bin_overflow")
@click.option("--target-r", type=float, default=0.70)
@click.option("--target-p", type=float, default=0.70)
@click.option("--inference-conf", type=float, default=0.001)
@click.option("--device", default="0")
@click.option("--out-json", type=click.Path(path_type=Path), required=True)
@click.option("--folds-only", type=int, multiple=True, default=None, help="Restrict to specific folds (e.g. 0 1 2)")
def main(weights_dir, folds_dir, target_class, target_class_name, target_r, target_p,
         inference_conf, device, out_json, folds_only):
    from ultralytics import YOLO

    # Find runs
    runs = []
    for best_pt in weights_dir.rglob("weights/best.pt"):
        run_dir = best_pt.parent.parent
        m = RUN_DIR_RE.search(run_dir.name)
        if not m:
            continue
        fold = int(m.group(1))
        if folds_only and fold not in folds_only:
            continue
        seed = int(m.group(2))
        runs.append((fold, seed, best_pt))

    runs.sort()
    click.echo(f"Found {len(runs)} runs. Target class={target_class_name} (id={target_class})")
    click.echo(f"Targets: R>={target_r}, P>={target_p}")

    results = {}
    for fold, seed, weights_path in runs:
        click.echo(f"\n[fold={fold} seed={seed}] inference at conf={inference_conf} ...")
        model = YOLO(str(weights_path))
        fold_dir = folds_dir / f"fold_{fold}"
        matched_preds, total_gt = collect_predictions(
            model, fold_dir, target_class, inference_conf, device
        )
        del model
        import torch
        torch.cuda.empty_cache()

        click.echo(f"  {len(matched_preds)} predictions, {total_gt} GT instances")
        curve = compute_pr_curve(matched_preds, total_gt)
        tuned = find_target_threshold(curve, target_r, target_p)

        if tuned:
            point = tuned["r_target_point"]
            if point:
                click.echo(f"  R>=0.70: threshold={point[0]:.3f}, P={point[1]:.3f}, R={point[2]:.3f}")
            f1p = tuned["best_f1_point"]
            if f1p:
                click.echo(f"  best F1={tuned['best_f1']:.3f} at threshold={f1p[0]:.3f}, P={f1p[1]:.3f}, R={f1p[2]:.3f}")

        results[f"fold_{fold}_seed_{seed}"] = {
            "fold": fold,
            "seed": seed,
            "n_predictions": len(matched_preds),
            "total_gt": total_gt,
            "r_target_point": tuned["r_target_point"] if tuned else None,
            "best_f1_point": tuned["best_f1_point"] if tuned else None,
            "best_f1": tuned["best_f1"] if tuned else None,
        }

    # Aggregate LOSO mean
    r_target_p = [r["r_target_point"][1] for r in results.values() if r["r_target_point"]]
    best_f1s = [r["best_f1"] for r in results.values() if r["best_f1"] is not None]
    if r_target_p:
        import statistics
        agg = {
            "n_runs_satisfying_R_target": len(r_target_p),
            "mean_P_at_R_target": statistics.mean(r_target_p),
            "std_P_at_R_target": statistics.stdev(r_target_p) if len(r_target_p) > 1 else 0,
            "mean_best_f1": statistics.mean(best_f1s) if best_f1s else 0,
            "std_best_f1": statistics.stdev(best_f1s) if len(best_f1s) > 1 else 0,
        }
        click.echo(f"\n=== Aggregate ({len(results)} runs) ===")
        click.echo(f"At R>={target_r}: mean P = {agg['mean_P_at_R_target']:.3f} ± {agg['std_P_at_R_target']:.3f}")
        click.echo(f"Best F1: mean = {agg['mean_best_f1']:.3f} ± {agg['std_best_f1']:.3f}")
    else:
        agg = {}

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps({"runs": results, "aggregate": agg,
                                    "target_class": target_class_name,
                                    "target_r": target_r,
                                    "target_p": target_p}, indent=2))
    click.echo(f"\nSaved: {out_json}")


if __name__ == "__main__":
    main()
