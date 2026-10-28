"""Factorial F1(bin_overflow) eval for yolo_loso_1920_b6 — apples-to-apples vs yolo 1280.

For each (fold, seed) in 5×3 matrix:
  - Load best.pt
  - Predict on val images at conf=0.001, iou=<NMS> NMS (default 0.4 to match prior yolo evals)
  - Apply ROI filter: drop predictions whose centre is outside cameras_roi.json rect
  - Apply ROI filter to GT bin_overflow boxes too
  - Greedy match preds → GTs at matching_iou >= 0.5
  - Compute F1(bin_overflow) at:
      * sweep (best of conf threshold scan) — optimistic ceiling
      * fixed @ conf=0.25 — deployable

Aggregate:
  - Per-fold mean ± std across seeds
  - LOSO mean ± std across folds

Output JSON for easy ingestion + printed table.

Usage on 4090:
    cd /home/alex/dumps_monitoring/ml
    source venv/bin/activate
    python scripts/analysis/factorial_yolo_1920_b6.py \\
        --runs-root runs/detect/runs/yolo_loso_1920_b6 \\
        --folds-dir data/folds \\
        --roi-config configs/cameras_roi.json \\
        --nms-iou 0.4 \\
        --matching-iou 0.5 \\
        --target-class 1 \\
        --out-json runs/analysis/factorial_yolo_1920_b6.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from statistics import mean, stdev

import click


RUN_DIR_RE = re.compile(r"fold_(\d+)_seed_(\d+)$")
FOLD_TO_CAM = {0: "1", 1: "2", 2: "3", 3: "5", 4: "7"}


def box_iou(a, b):
    ax1, ay1, ax2, ay2 = a[:4]
    bx1, by1, bx2, by2 = b[:4]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    aarea = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    barea = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = aarea + barea - inter
    return inter / union if union > 0 else 0.0


def load_roi_rects(roi_config: Path, camera: str) -> list[tuple[float, float, float, float]]:
    cfg = json.loads(roi_config.read_text())
    val = cfg.get(camera)
    if val is None:
        raise KeyError(f"No ROI for camera {camera}")
    if isinstance(val, list) and val and isinstance(val[0], (int, float)):
        return [tuple(val)]  # single rect
    return [tuple(r) for r in val]


def inside_roi(bx1, by1, bx2, by2, rects) -> bool:
    cx, cy = (bx1 + bx2) / 2, (by1 + by2) / 2
    for rx1, ry1, rx2, ry2 in rects:
        if rx1 <= cx <= rx2 and ry1 <= cy <= ry2:
            return True
    return False


def eval_one_run(
    weights: Path,
    fold_dir: Path,
    cam: str,
    rects: list,
    target_class: int,
    nms_iou: float,
    matching_iou: float,
    inference_conf: float,
    device: str,
) -> dict:
    """Run inference + ROI filter + greedy matching. Return matched_preds + total_gt."""
    from PIL import Image
    from ultralytics import YOLO

    model = YOLO(str(weights))

    val_images_dir = fold_dir / "images" / "val"
    val_labels_dir = fold_dir / "labels" / "val"
    val_frames = sorted(val_images_dir.glob(f"cam{cam}_*.jpg"))

    matched_preds: list[tuple[float, bool]] = []  # (conf, is_tp)
    total_gt_inside_roi = 0
    n_pred_in = 0
    n_pred_out = 0

    for img_path in val_frames:
        with Image.open(img_path) as im:
            W, H = im.size

        # Load GT, keep only target class, only inside ROI
        gts_inside = []
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
                if inside_roi(x1, y1, x2, y2, rects):
                    gts_inside.append((x1, y1, x2, y2))
        total_gt_inside_roi += len(gts_inside)

        # Inference
        results = model.predict(
            source=str(img_path),
            device=device,
            verbose=False,
            save=False,
            conf=inference_conf,
            iou=nms_iou,
        )
        r = results[0]
        if r.boxes is None or len(r.boxes) == 0:
            continue

        xyxy = r.boxes.xyxy.cpu().numpy()
        cls_arr = r.boxes.cls.cpu().numpy().astype(int)
        conf_arr = r.boxes.conf.cpu().numpy()

        preds = []
        for i in range(len(xyxy)):
            if int(cls_arr[i]) != target_class:
                continue
            box = (float(xyxy[i, 0]), float(xyxy[i, 1]), float(xyxy[i, 2]), float(xyxy[i, 3]))
            preds.append((box, float(conf_arr[i])))

        # ROI filter
        preds_inside = [p for p in preds if inside_roi(*p[0], rects)]
        n_pred_in += len(preds_inside)
        n_pred_out += len(preds) - len(preds_inside)

        # Greedy match by descending conf
        preds_inside.sort(key=lambda p: -p[1])
        gt_matched = [False] * len(gts_inside)
        for (pbox, pconf) in preds_inside:
            best_iou, best_j = 0.0, -1
            for j, g in enumerate(gts_inside):
                if gt_matched[j]:
                    continue
                iou_val = box_iou(pbox, g)
                if iou_val > best_iou:
                    best_iou, best_j = iou_val, j
            is_tp = best_j >= 0 and best_iou >= matching_iou
            if is_tp:
                gt_matched[best_j] = True
            matched_preds.append((pconf, is_tp))

    return {
        "matched_preds": matched_preds,
        "total_gt": total_gt_inside_roi,
        "n_pred_in": n_pred_in,
        "n_pred_out": n_pred_out,
        "n_val_frames": len(val_frames),
    }


def compute_pr_metrics(matched_preds, total_gt, fixed_conf=0.25):
    """Return (best_sweep_f1, fixed_f1, fixed_p, fixed_r)."""
    if not matched_preds or total_gt == 0:
        return 0.0, 0.0, 0.0, 0.0

    sorted_preds = sorted(matched_preds, key=lambda x: -x[0])

    # sweep — find best F1 across all thresholds
    tp = fp = 0
    best_f1 = 0.0
    for conf, is_tp in sorted_preds:
        if is_tp:
            tp += 1
        else:
            fp += 1
        p = tp / (tp + fp) if (tp + fp) > 0 else 0
        r = tp / total_gt
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
        if f1 > best_f1:
            best_f1 = f1

    # fixed — apply conf >= fixed_conf threshold
    tp = sum(1 for (c, is_tp) in matched_preds if c >= fixed_conf and is_tp)
    fp = sum(1 for (c, is_tp) in matched_preds if c >= fixed_conf and not is_tp)
    fn = max(0, total_gt - tp)
    fixed_p = tp / (tp + fp) if (tp + fp) > 0 else 0
    fixed_r = tp / total_gt
    fixed_f1 = 2 * fixed_p * fixed_r / (fixed_p + fixed_r) if (fixed_p + fixed_r) > 0 else 0

    return best_f1, fixed_f1, fixed_p, fixed_r


@click.command()
@click.option("--runs-root", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--folds-dir", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--roi-config", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--nms-iou", type=float, default=0.4)
@click.option("--matching-iou", type=float, default=0.5)
@click.option("--target-class", type=int, default=1, help="1=bin_overflow")
@click.option("--target-class-name", default="bin_overflow")
@click.option("--inference-conf", type=float, default=0.001)
@click.option("--fixed-conf", type=float, default=0.25)
@click.option("--device", default="0")
@click.option("--out-json", type=click.Path(path_type=Path), required=True)
def main(runs_root, folds_dir, roi_config, nms_iou, matching_iou, target_class,
         target_class_name, inference_conf, fixed_conf, device, out_json):
    # Find runs
    runs = []
    for best_pt in runs_root.rglob("weights/best.pt"):
        run_dir = best_pt.parent.parent
        if "_crashed" in run_dir.name:
            continue
        m = RUN_DIR_RE.search(run_dir.name)
        if not m:
            continue
        runs.append((int(m.group(1)), int(m.group(2)), best_pt))
    runs.sort()
    click.echo(f"Found {len(runs)} runs in {runs_root}")

    results = {}  # {fold: {seed: {sweep_f1, fixed_f1, fixed_p, fixed_r, total_gt, n_pred_in, n_pred_out}}}

    for fold, seed, best_pt in runs:
        cam = FOLD_TO_CAM[fold]
        rects = load_roi_rects(roi_config, cam)
        fold_dir = folds_dir / f"fold_{fold}"

        click.echo(f"  fold {fold} seed {seed} (cam_{cam}) — {best_pt}")
        run_info = eval_one_run(
            best_pt, fold_dir, cam, rects, target_class,
            nms_iou, matching_iou, inference_conf, device,
        )
        sweep_f1, fixed_f1, fixed_p, fixed_r = compute_pr_metrics(
            run_info["matched_preds"], run_info["total_gt"], fixed_conf
        )
        results.setdefault(fold, {})[seed] = {
            "sweep_f1": sweep_f1,
            "fixed_f1": fixed_f1,
            "fixed_p": fixed_p,
            "fixed_r": fixed_r,
            "total_gt": run_info["total_gt"],
            "n_pred_in": run_info["n_pred_in"],
            "n_pred_out": run_info["n_pred_out"],
            "n_val_frames": run_info["n_val_frames"],
        }
        click.secho(
            f"    sweep_F1={sweep_f1:.4f}  fixed@{fixed_conf}_F1={fixed_f1:.4f} (P={fixed_p:.3f} R={fixed_r:.3f}) "
            f"GT={run_info['total_gt']} preds_in={run_info['n_pred_in']} preds_out={run_info['n_pred_out']}",
            fg="green",
        )

    # Aggregate per-fold across seeds
    per_fold = {}
    for fold in sorted(results.keys()):
        seeds = results[fold]
        sweep_vals = [s["sweep_f1"] for s in seeds.values()]
        fixed_vals = [s["fixed_f1"] for s in seeds.values()]
        per_fold[fold] = {
            "cam": FOLD_TO_CAM[fold],
            "n_seeds": len(seeds),
            "sweep_f1_mean": mean(sweep_vals),
            "sweep_f1_std": stdev(sweep_vals) if len(sweep_vals) > 1 else 0.0,
            "fixed_f1_mean": mean(fixed_vals),
            "fixed_f1_std": stdev(fixed_vals) if len(fixed_vals) > 1 else 0.0,
            "per_seed": seeds,
        }

    # LOSO across folds
    if per_fold:
        loso_sweep = [pf["sweep_f1_mean"] for pf in per_fold.values()]
        loso_fixed = [pf["fixed_f1_mean"] for pf in per_fold.values()]
        loso = {
            "sweep_f1_mean": mean(loso_sweep),
            "sweep_f1_std": stdev(loso_sweep) if len(loso_sweep) > 1 else 0.0,
            "fixed_f1_mean": mean(loso_fixed),
            "fixed_f1_std": stdev(loso_fixed) if len(loso_fixed) > 1 else 0.0,
        }
    else:
        loso = {}

    out = {
        "config": {
            "runs_root": str(runs_root),
            "nms_iou": nms_iou,
            "matching_iou": matching_iou,
            "target_class": target_class,
            "target_class_name": target_class_name,
            "inference_conf": inference_conf,
            "fixed_conf": fixed_conf,
            "roi_config": str(roi_config),
        },
        "per_fold": per_fold,
        "loso": loso,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(out, indent=2, default=lambda o: list(o) if hasattr(o, "__iter__") else str(o)))

    click.echo()
    click.echo("=" * 75)
    click.echo(f"PER-FOLD ({target_class_name}, NMS_iou={nms_iou}, match_iou={matching_iou})")
    click.echo("=" * 75)
    click.echo(f"{'fold':<5} {'cam':<5} {'sweep_F1 μ±σ':>20} {'fixed_F1 μ±σ':>20}")
    for fold in sorted(per_fold.keys()):
        pf = per_fold[fold]
        click.echo(
            f"{fold:<5} cam_{pf['cam']:<3} "
            f"{pf['sweep_f1_mean']:>10.4f}±{pf['sweep_f1_std']:.4f}    "
            f"{pf['fixed_f1_mean']:>10.4f}±{pf['fixed_f1_std']:.4f}"
        )

    click.echo()
    click.echo("=" * 75)
    click.echo("LOSO MEAN")
    click.echo("=" * 75)
    click.echo(f"  sweep F1 (best-of-scan):  {loso['sweep_f1_mean']:.4f} ± {loso['sweep_f1_std']:.4f}")
    click.echo(f"  fixed F1 (@{fixed_conf}):    {loso['fixed_f1_mean']:.4f} ± {loso['fixed_f1_std']:.4f}")
    click.echo(f"\nJSON saved: {out_json}")


if __name__ == "__main__":
    main()
