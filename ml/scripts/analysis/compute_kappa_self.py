"""Compute intra-annotator agreement (Cohen's κ_self) on re-annotated frames.

Input:
- Original labels (data/processed/labeled/<cam>/<stem>.txt)
- Re-annotated labels (separate dir, e.g. data/processed/reannotated/<cam>/<stem>.txt)

For each frame, we match original bboxes to re-annotated bboxes by IoU>=0.5.
Then we compute Cohen's κ per class for the class assignment of matched bboxes,
treating un-matched bboxes as "extra" with class=background.

Usage:
    python compute_kappa_self.py \\
        --original-labels data/processed/labeled/2 \\
        --reannotated-labels data/processed/reannotated/2 \\
        --images-dir data/processed/to_label/2 \\
        --out-json runs/analysis/kappa_self_cam_2.json
"""

from __future__ import annotations

import json
from pathlib import Path

import click


CLASS_NAMES = {0: "bin_ok", 1: "bin_overflow", 2: "ground_trash", -1: "background"}


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


def load_yolo_bboxes(label_path: Path, W: int, H: int):
    """Returns list of (x1,y1,x2,y2,cls)."""
    if not label_path.exists() or label_path.stat().st_size == 0:
        return []
    out = []
    for line in label_path.read_text().strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split()
        cls = int(parts[0])
        cx, cy, w_n, h_n = map(float, parts[1:5])
        x1 = (cx - w_n / 2) * W
        y1 = (cy - h_n / 2) * H
        x2 = (cx + w_n / 2) * W
        y2 = (cy + h_n / 2) * H
        out.append((x1, y1, x2, y2, cls))
    return out


def cohen_kappa(pairs: list[tuple[int, int]], classes: list[int]) -> float:
    """Standard Cohen's κ on paired (rater1_class, rater2_class)."""
    n = len(pairs)
    if n == 0:
        return 1.0  # vacuous
    # Observed agreement
    p_o = sum(1 for a, b in pairs if a == b) / n
    # Expected agreement (random)
    p_e = 0.0
    for cls in classes:
        p_a = sum(1 for a, _ in pairs if a == cls) / n
        p_b = sum(1 for _, b in pairs if b == cls) / n
        p_e += p_a * p_b
    if p_e == 1.0:
        return 1.0
    return (p_o - p_e) / (1 - p_e)


@click.command()
@click.option("--original-labels", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--reannotated-labels", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--images-dir", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--iou-threshold", type=float, default=0.5)
@click.option("--out-json", type=click.Path(path_type=Path), required=True)
def main(original_labels, reannotated_labels, images_dir, iou_threshold, out_json):
    from PIL import Image

    label_files = sorted(reannotated_labels.glob("*.txt"))
    click.echo(f"Found {len(label_files)} re-annotated label files")

    pairs = []  # (original_cls, reannotated_cls), including background=-1 for unmatched
    matched_count = 0
    unmatched_in_orig = 0  # bbox in original but not in re-annotation
    unmatched_in_reann = 0  # bbox in re-annotation but not in original
    bbox_count_orig = 0
    bbox_count_reann = 0

    for reann_lbl in label_files:
        stem = reann_lbl.stem
        img_path = images_dir / (stem + ".jpg")
        if not img_path.exists():
            click.echo(f"  ! no image for {stem}")
            continue
        with Image.open(img_path) as im:
            W, H = im.size

        orig_lbl = original_labels / reann_lbl.name
        orig_boxes = load_yolo_bboxes(orig_lbl, W, H)
        reann_boxes = load_yolo_bboxes(reann_lbl, W, H)
        bbox_count_orig += len(orig_boxes)
        bbox_count_reann += len(reann_boxes)

        # Greedy match by IoU
        reann_matched = [False] * len(reann_boxes)
        for o in orig_boxes:
            best_iou, best_j = 0.0, -1
            for j, r in enumerate(reann_boxes):
                if reann_matched[j]:
                    continue
                iou = box_iou(o[:4], r[:4])
                if iou > best_iou:
                    best_iou, best_j = iou, j
            if best_j >= 0 and best_iou >= iou_threshold:
                reann_matched[best_j] = True
                pairs.append((o[4], reann_boxes[best_j][4]))
                matched_count += 1
            else:
                pairs.append((o[4], -1))  # orig bbox, no reann match → reann said "nothing"
                unmatched_in_orig += 1
        for j, m in enumerate(reann_matched):
            if not m:
                pairs.append((-1, reann_boxes[j][4]))  # extra bbox in reann
                unmatched_in_reann += 1

    # Cohen's κ overall (3 classes + background)
    classes = [0, 1, 2, -1]
    k_overall = cohen_kappa(pairs, classes)

    # Per-class κ (binary: class X vs not-X)
    per_class = {}
    for cls in [0, 1, 2]:
        binary_pairs = [(int(a == cls), int(b == cls)) for a, b in pairs]
        per_class[CLASS_NAMES[cls]] = cohen_kappa(binary_pairs, [0, 1])

    summary = {
        "n_frames_reannotated": len(label_files),
        "n_bboxes_original": bbox_count_orig,
        "n_bboxes_reannotated": bbox_count_reann,
        "matched": matched_count,
        "unmatched_in_original": unmatched_in_orig,
        "unmatched_in_reannotated": unmatched_in_reann,
        "iou_threshold": iou_threshold,
        "kappa_overall_4class": k_overall,
        "kappa_per_class_binary": per_class,
    }

    click.echo("\n=== Intra-annotator Cohen's κ_self ===")
    click.echo(f"Frames re-annotated: {summary['n_frames_reannotated']}")
    click.echo(f"Bboxes original/reann: {bbox_count_orig}/{bbox_count_reann}")
    click.echo(f"Matched: {matched_count}, unmatched (orig only): {unmatched_in_orig}, (reann only): {unmatched_in_reann}")
    click.echo(f"\nκ_overall (4-class incl. bg): {k_overall:.3f}")
    click.echo("κ per class (binary):")
    for cls, k in per_class.items():
        cohort = "substantial" if k >= 0.7 else "moderate" if k >= 0.4 else "low"
        click.echo(f"  {cls:<15}: {k:.3f} ({cohort})")

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2))
    click.echo(f"\nSaved: {out_json}")


if __name__ == "__main__":
    main()
