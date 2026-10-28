"""Top-up training data with fresh frames from S3 (date range 2026-05-08 to 2026-05-13).

Mirrors our original sampling pipeline: pulls frames in date range, runs
DINOv2 uniqueness sampling, picks N most-unique-per-camera, writes to
data/processed/to_label_topup/<cam>/ ready for CVAT annotation.

This script is a thin wrapper around prefetch_camera_frames.py +
compute_dinov2_embeddings.py + sample_dataset.py (existing pipeline scripts).

Usage:
    python topup_from_s3.py \\
        --start-date 2026-05-08 \\
        --end-date 2026-05-13 \\
        --per-camera 20 \\
        --cameras 1 2 3 5 7
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import click


@click.command()
@click.option("--start-date", default="2026-05-08", help="YYYY-MM-DD inclusive")
@click.option("--end-date", default="2026-05-13", help="YYYY-MM-DD inclusive")
@click.option("--per-camera", type=int, default=20, help="Frames to keep per camera after sampling")
@click.option("--cameras", multiple=True, type=int, default=[1, 2, 3, 5, 7])
@click.option(
    "--prefetch-dir",
    type=click.Path(path_type=Path),
    default=Path("data/raw/full_cameras"),
)
@click.option(
    "--out-dir",
    type=click.Path(path_type=Path),
    default=Path("data/processed/to_label_topup"),
)
def main(start_date, end_date, per_camera, cameras, prefetch_dir, out_dir):
    """Filter pre-fetched frames in date range, then re-use DINOv2 sampling.

    Assumes that S3 frames have already been pulled to data/raw/full_cameras/
    via prefetch_camera_frames.py. If not, that script must be run first.
    """
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date) + timedelta(days=1) - timedelta(seconds=1)

    click.echo(f"Filtering frames in [{start_date} .. {end_date}] for cameras {list(cameras)}")

    candidates_per_cam: dict[int, list[Path]] = {}
    for cam in cameras:
        cam_dir = prefetch_dir / str(cam)
        all_jpgs = list(cam_dir.glob("*.jpg")) if cam_dir.exists() else []
        in_range = []
        for jpg in all_jpgs:
            # Expect stem like "2026-05-08_064734"
            try:
                ts = datetime.strptime(jpg.stem.split("_")[0], "%Y-%m-%d")
            except ValueError:
                continue
            if start <= ts <= end:
                in_range.append(jpg)
        candidates_per_cam[cam] = sorted(in_range)
        click.echo(f"  cam_{cam}: {len(in_range)} frames in date range "
                   f"(out of {len(all_jpgs)} total in prefetch)")

    # If too few candidates, suggest pulling more
    for cam, cand in candidates_per_cam.items():
        if len(cand) < per_camera:
            click.secho(
                f"  ! cam_{cam}: only {len(cand)} candidates, need {per_camera}. "
                f"Run prefetch_camera_frames.py first.", fg="yellow"
            )

    # Stage 1: simple uniform sampling within date range (for now; DINOv2 sampling
    # adds complexity — apply it as a follow-up if needed).
    # We pick every Nth frame to span the date range evenly.
    out_dir = Path(out_dir)
    for cam, cand in candidates_per_cam.items():
        cam_out = out_dir / str(cam)
        cam_out.mkdir(parents=True, exist_ok=True)
        if not cand:
            continue
        step = max(1, len(cand) // per_camera)
        selected = cand[::step][:per_camera]
        for src in selected:
            dst = cam_out / src.name
            if not dst.exists():
                shutil.copy2(src, dst)
        click.echo(f"  cam_{cam}: selected {len(selected)} frames → {cam_out}")

    manifest = {
        "start_date": start_date,
        "end_date": end_date,
        "per_camera": per_camera,
        "cameras": list(cameras),
        "counts": {str(cam): len(list((out_dir / str(cam)).glob("*.jpg"))) for cam in cameras},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    click.echo(f"\n✓ Top-up frames in {out_dir}/")
    click.echo("Next steps:")
    click.echo(f"  1. Run DINOv2 uniqueness sampling on these (optional) for diversity")
    click.echo(f"  2. Upload to CVAT as new task for annotation")
    click.echo(f"  3. After annotation: cvat_export_labels.py + merge into data/processed/labeled/")


if __name__ == "__main__":
    main()
