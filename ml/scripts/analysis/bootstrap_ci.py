"""Bootstrap confidence intervals over LOSO results.

Two modes:
  - per-image (IID): resample images within each fold's val set, recompute mAP/F1.
    Defends against random val-set composition variance.
  - block (camera, date): resample blocks of (camera, date) pairs.
    Defends against temporal correlation — adjacent hourly frames are NOT IID.

Block bootstrap is what we report for headline LOSO numbers per adversarial v2.

Usage:
    python bootstrap_ci.py \\
        --runs-root runs/detect/runs/level1 \\
        --folds-dir data/folds \\
        --n-iters 1000 \\
        --mode block \\
        --out-json bootstrap_ci.json
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import click
import numpy as np
import torch


RUN_DIR_RE = re.compile(r"fold_(\d+)_seed_(\d+)$")
DATE_FROM_STEM_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def find_runs(runs_root: Path) -> list[tuple[str, int, int, Path]]:
    out = []
    for best_pt in runs_root.rglob("weights/best.pt"):
        run_dir = best_pt.parent.parent
        m = RUN_DIR_RE.search(run_dir.name)
        if not m:
            continue
        out.append((run_dir.parent.name, int(m.group(1)), int(m.group(2)), best_pt))
    return out


def predict_per_image(model, val_images: list[Path], device: str) -> dict[str, dict]:
    """Run inference on each val image, return per-image preds + ground truth.

    For each image returns:
        boxes_pred: list of (x1, y1, x2, y2, cls, conf)
        boxes_gt: list of (x1, y1, x2, y2, cls)  (read from neighbouring .txt label)
    """
    out = {}
    for img_path in val_images:
        results = model.predict(
            source=str(img_path),
            device=device,
            verbose=False,
            save=False,
            conf=0.001,  # capture all so threshold sweep works downstream
            iou=0.7,
        )
        r = results[0]
        boxes_pred = []
        if r.boxes is not None and len(r.boxes) > 0:
            xyxy = r.boxes.xyxy.cpu().numpy()
            cls = r.boxes.cls.cpu().numpy().astype(int)
            conf = r.boxes.conf.cpu().numpy()
            for i in range(len(xyxy)):
                boxes_pred.append(
                    (
                        float(xyxy[i, 0]), float(xyxy[i, 1]),
                        float(xyxy[i, 2]), float(xyxy[i, 3]),
                        int(cls[i]), float(conf[i]),
                    )
                )

        # GT — find label file: replace /images/ with /labels/ and .jpg with .txt
        label_path = Path(
            str(img_path).replace("/images/", "/labels/").rsplit(".", 1)[0] + ".txt"
        )
        boxes_gt = []
        if label_path.exists():
            w = r.orig_shape[1] if hasattr(r, "orig_shape") else None
            h = r.orig_shape[0] if hasattr(r, "orig_shape") else None
            if w is None or h is None:
                # fallback: read image to get dims
                from PIL import Image
                with Image.open(img_path) as im:
                    w, h = im.size
            for line in label_path.read_text().strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split()
                cls = int(parts[0])
                cx, cy, bw, bh = map(float, parts[1:5])
                x1 = (cx - bw / 2) * w
                y1 = (cy - bh / 2) * h
                x2 = (cx + bw / 2) * w
                y2 = (cy + bh / 2) * h
                boxes_gt.append((x1, y1, x2, y2, cls))

        out[img_path.stem] = {
            "boxes_pred": boxes_pred,
            "boxes_gt": boxes_gt,
            "image": str(img_path),
        }
    return out


def compute_pr_at_iou(
    image_data: dict[str, dict], iou_threshold: float = 0.5, conf_threshold: float = 0.25
) -> tuple[float, float, float]:
    """Aggregate TP/FP/FN across given images, return overall (P, R, F1)."""
    tp = fp = fn = 0
    for stem, d in image_data.items():
        gts = list(d["boxes_gt"])  # (x1,y1,x2,y2,cls)
        preds = [p for p in d["boxes_pred"] if p[5] >= conf_threshold]
        # Greedy match: sort preds by conf desc, match each to best-IoU unmatched GT
        preds.sort(key=lambda p: -p[5])
        gt_matched = [False] * len(gts)
        for p in preds:
            px1, py1, px2, py2, pc, _ = p
            best_iou = 0.0
            best_idx = -1
            for j, g in enumerate(gts):
                if gt_matched[j] or g[4] != pc:
                    continue
                iou = box_iou((px1, py1, px2, py2), g[:4])
                if iou > best_iou:
                    best_iou, best_idx = iou, j
            if best_idx >= 0 and best_iou >= iou_threshold:
                gt_matched[best_idx] = True
                tp += 1
            else:
                fp += 1
        fn += sum(1 for m in gt_matched if not m)
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return p, r, f1


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


def bootstrap_ci(
    image_data: dict[str, dict],
    n_iters: int = 1000,
    mode: str = "iid",
    iou_threshold: float = 0.5,
    conf_threshold: float = 0.25,
    rng_seed: int = 0,
) -> dict:
    """Bootstrap (P, R, F1) CI by resampling.

    mode='iid' resamples individual images.
    mode='block' resamples (camera, date) groups inferred from filename stems.
    """
    rng = np.random.default_rng(rng_seed)
    keys = list(image_data.keys())
    if mode == "block":
        block_to_keys: dict[str, list[str]] = defaultdict(list)
        for k in keys:
            # stem like "2026-04-25_234734" → date = "2026-04-25"
            m = DATE_FROM_STEM_RE.match(k)
            date = m.group(1) if m else "unknown"
            # camera id is in the parent path; we don't have it here, assume single fold
            block_to_keys[date].append(k)
        blocks = list(block_to_keys.keys())

    p_samples, r_samples, f1_samples = [], [], []
    n = len(keys)
    for _ in range(n_iters):
        if mode == "iid":
            sampled = rng.choice(n, size=n, replace=True)
            sample_data = {keys[i]: image_data[keys[i]] for i in sampled}
        else:
            sampled_blocks = rng.choice(len(blocks), size=len(blocks), replace=True)
            sampled_keys = []
            for b_idx in sampled_blocks:
                sampled_keys.extend(block_to_keys[blocks[b_idx]])
            sample_data = {f"{k}_{i}": image_data[k] for i, k in enumerate(sampled_keys)}
        p, r, f1 = compute_pr_at_iou(sample_data, iou_threshold, conf_threshold)
        p_samples.append(p)
        r_samples.append(r)
        f1_samples.append(f1)

    return {
        "P_mean": float(np.mean(p_samples)),
        "P_ci_lo": float(np.percentile(p_samples, 2.5)),
        "P_ci_hi": float(np.percentile(p_samples, 97.5)),
        "R_mean": float(np.mean(r_samples)),
        "R_ci_lo": float(np.percentile(r_samples, 2.5)),
        "R_ci_hi": float(np.percentile(r_samples, 97.5)),
        "F1_mean": float(np.mean(f1_samples)),
        "F1_ci_lo": float(np.percentile(f1_samples, 2.5)),
        "F1_ci_hi": float(np.percentile(f1_samples, 97.5)),
        "n_iters": n_iters,
        "mode": mode,
    }


@click.command()
@click.option("--runs-root", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--folds-dir", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--n-iters", type=int, default=1000)
@click.option("--mode", type=click.Choice(["iid", "block"]), default="block")
@click.option("--iou-threshold", type=float, default=0.5)
@click.option("--conf-threshold", type=float, default=0.25)
@click.option("--device", default="0")
@click.option("--out-json", type=click.Path(path_type=Path), default=Path("bootstrap_ci.json"))
def main(
    runs_root: Path,
    folds_dir: Path,
    n_iters: int,
    mode: str,
    iou_threshold: float,
    conf_threshold: float,
    device: str,
    out_json: Path,
) -> None:
    from ultralytics import YOLO

    runs = find_runs(runs_root)
    by_fold: dict = {}
    for config, fold, seed, best_pt in sorted(runs):
        click.echo(f"\n[{config} fold={fold} seed={seed}] inference on val ...")
        val_images_dir = folds_dir / f"fold_{fold}" / "images" / "val"
        val_images = sorted(val_images_dir.glob("*.jpg"))
        if not val_images:
            click.echo(f"  no val images at {val_images_dir}")
            continue

        model = YOLO(str(best_pt))
        image_data = predict_per_image(model, val_images, device)
        del model
        torch.cuda.empty_cache()

        click.echo(f"  bootstrap ({mode}, n_iters={n_iters}) ...")
        ci = bootstrap_ci(image_data, n_iters, mode, iou_threshold, conf_threshold, rng_seed=seed)
        ci["config"] = config
        ci["fold"] = fold
        ci["seed"] = seed
        click.echo(
            f"  F1={ci['F1_mean']:.3f} [{ci['F1_ci_lo']:.3f}, {ci['F1_ci_hi']:.3f}]  "
            f"P={ci['P_mean']:.3f} [{ci['P_ci_lo']:.3f}, {ci['P_ci_hi']:.3f}]  "
            f"R={ci['R_mean']:.3f} [{ci['R_ci_lo']:.3f}, {ci['R_ci_hi']:.3f}]"
        )
        by_fold.setdefault((config, fold), []).append(ci)

    out_data = {
        f"{cfg}__fold_{fold}": items for (cfg, fold), items in by_fold.items()
    }
    out_json.write_text(json.dumps(out_data, indent=2))
    click.echo(f"\nSaved: {out_json}")


if __name__ == "__main__":
    main()
