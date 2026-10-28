"""Zero-shot qualitative inference on cam_6 (excluded from training).

Cam_6 was rejected from the LOSO training set as unfit (poor angle, no bin
proxy in COCO audit). After Level-1 training, we run inference on a random
sample of cam_6 frames to see if the model generalises to unseen cameras.

Per todo_post_labeling.md: 100 random frames, save predictions, manual review
of 20-30. Reported in Ch5 §5.4 "Qualitative cross-camera transfer".

Usage:
    python cam6_zero_shot.py \\
        --weights runs/detect/runs/level1/level1_baseline/fold_0_seed_0/weights/best.pt \\
        --cam6-dir data/raw/full_cameras/6 \\
        --n-frames 100 \\
        --out-dir runs/cam6_zero_shot
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import click


@click.command()
@click.option("--weights", type=click.Path(path_type=Path, exists=True), required=True)
@click.option(
    "--cam6-dir",
    type=click.Path(path_type=Path, exists=True),
    default=Path("data/raw/full_cameras/6"),
)
@click.option("--n-frames", type=int, default=100)
@click.option("--seed", type=int, default=42)
@click.option("--device", default="0")
@click.option(
    "--out-dir",
    type=click.Path(path_type=Path),
    default=Path("runs/cam6_zero_shot"),
)
@click.option("--conf", type=float, default=0.25)
def main(
    weights: Path,
    cam6_dir: Path,
    n_frames: int,
    seed: int,
    device: str,
    out_dir: Path,
    conf: float,
) -> None:
    from ultralytics import YOLO

    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)

    all_jpgs = sorted(cam6_dir.glob("*.jpg"))
    if not all_jpgs:
        # try recursive
        all_jpgs = sorted(cam6_dir.rglob("*.jpg"))
    if not all_jpgs:
        click.echo(f"No jpgs found under {cam6_dir}")
        return
    click.echo(f"Found {len(all_jpgs)} cam_6 frames; sampling {n_frames}")

    sampled = rng.sample(all_jpgs, min(n_frames, len(all_jpgs)))

    click.echo(f"Loading {weights}")
    model = YOLO(str(weights))

    summary = {
        "weights": str(weights),
        "n_frames_inspected": len(sampled),
        "conf_threshold": conf,
        "frames": [],
        "totals": {"detections": 0, "by_class": {}},
    }

    for idx, img_path in enumerate(sampled):
        results = model.predict(
            source=str(img_path),
            device=device,
            verbose=False,
            save=True,
            project=str(out_dir),
            name="predictions",
            exist_ok=True,
            conf=conf,
            iou=0.7,
        )
        r = results[0]
        n_det = len(r.boxes) if r.boxes is not None else 0
        per_class: dict[str, int] = {}
        if r.boxes is not None and n_det > 0:
            cls = r.boxes.cls.cpu().numpy().astype(int)
            for c in cls:
                name = model.names[int(c)]
                per_class[name] = per_class.get(name, 0) + 1
                summary["totals"]["by_class"][name] = (
                    summary["totals"]["by_class"].get(name, 0) + 1
                )
        summary["frames"].append(
            {"path": str(img_path), "n_detections": n_det, "per_class": per_class}
        )
        summary["totals"]["detections"] += n_det
        if (idx + 1) % 20 == 0:
            click.echo(f"  {idx + 1}/{len(sampled)} processed, detections so far: {summary['totals']['detections']}")

    n = len(sampled)
    avg_dets = summary["totals"]["detections"] / n if n > 0 else 0
    click.echo(
        f"\n=== Cam_6 zero-shot summary ==="
        f"\n  N frames inspected: {n}"
        f"\n  Total detections: {summary['totals']['detections']}"
        f"\n  Avg detections/frame: {avg_dets:.2f}"
        f"\n  By class: {summary['totals']['by_class']}"
        f"\n  Visualisations: {out_dir / 'predictions'}"
    )

    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    click.echo(f"  Summary JSON: {summary_path}")


if __name__ == "__main__":
    main()
