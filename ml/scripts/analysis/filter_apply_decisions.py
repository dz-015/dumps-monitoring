"""Apply decisions CSV from build_review_gallery.py: move dropped frames to /dropped/.

Reads decisions CSV with columns:
    filename, n_bboxes, n_bin_ok, n_bin_overflow, n_ground_trash, action, note

For each row with action in {drop, relabel}, moves the image and label files
to a `_dropped/<reason>/` directory so they're excluded from training. Also
applies pre-specified criteria if --pre-specified flag is set:
    1. renovation_window: 2026-02-26 to 2026-03-27 09:00
    2. fewer_than_2_bins: total bin instances < 2
    3. dark_frame: mean V channel < 0.15

Usage:
    # Apply ONLY manual decisions:
    python filter_apply_decisions.py \\
        --decisions runs/manual_review/cam_2/decisions.csv \\
        --camera 2 \\
        --apply manual

    # Apply ONLY pre-specified criteria across all cameras:
    python filter_apply_decisions.py \\
        --camera 2 --camera 3 --camera 5 --camera 7 --camera 1 \\
        --apply pre-specified
"""

from __future__ import annotations

import csv
import re
import shutil
from datetime import datetime
from pathlib import Path

import click


WORKING_CAMERAS = [1, 2, 3, 5, 7]
# cam_2-specific: documented renovation period during which construction
# debris was annotated inconsistently and bins were moved.
RENOVATION_WINDOW_START = datetime(2026, 2, 26, 0, 0, 0)
RENOVATION_WINDOW_END = datetime(2026, 3, 27, 9, 0, 0)
# per-camera mean bins/frame (computed from labels) and threshold = ceil(mean/2).
# Frames with fewer than threshold bins are dropped (under-labelled / unhelpful).
CAM_MEAN_BINS = {1: 1.5, 2: 6.8, 3: 8.1, 5: 2.3, 7: 1.4}


def parse_stem_to_datetime(stem: str) -> datetime | None:
    """Stem like '2026-04-25_234734' or 'cam2_2026-03-04_123439' etc."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})[_-](\d{6})", stem)
    if not m:
        return None
    date_str, time_str = m.group(1), m.group(2)
    try:
        return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H%M%S")
    except ValueError:
        return None


def in_renovation_window(stem: str) -> bool:
    ts = parse_stem_to_datetime(stem)
    if ts is None:
        return False
    return RENOVATION_WINDOW_START <= ts <= RENOVATION_WINDOW_END


def bins_below_half_mean(label_path: Path, cam: int) -> int | None:
    """Returns n_bins if below threshold ceil(mean/2), else None."""
    import math
    n_bins, _ = count_bboxes(label_path)
    threshold = math.ceil(CAM_MEAN_BINS.get(cam, 1) / 2)
    if n_bins < threshold:
        return n_bins
    return None


def count_bboxes(label_path: Path) -> tuple[int, int]:
    """Returns (n_bins, n_total) where bins = classes 0/1."""
    if not label_path.exists() or label_path.stat().st_size == 0:
        return 0, 0
    n_bins = n_total = 0
    for line in label_path.read_text().strip().split("\n"):
        if not line.strip():
            continue
        cls = int(line.split()[0])
        n_total += 1
        if cls in (0, 1):
            n_bins += 1
    return n_bins, n_total


# File moves are deprecated — they break in-flight training that uses symlinks
# to data/processed/to_label/<cam>/. We now write an exclusion list instead;
# prepare_loso_fold.py reads it and skips matching files at fold preparation.


@click.command()
@click.option("--decisions", type=click.Path(path_type=Path), default=None,
              help="Decisions CSV from build_review_gallery (action column).")
@click.option("--camera", "cameras", type=int, multiple=True, required=True)
@click.option("--apply",
              type=click.Choice(["manual", "pre-specified", "both"]),
              default="both")
@click.option("--images-dir", type=click.Path(path_type=Path, exists=True),
              default=Path("data/processed/to_label"))
@click.option("--labels-dir", type=click.Path(path_type=Path, exists=True),
              default=Path("data/processed/labeled"))
@click.option("--exclude-list-out", type=click.Path(path_type=Path),
              default=Path("data/processed/cam_2_excluded.txt"),
              help="Plain-text file with one filename per line. Empty input keeps file untouched.")
@click.option("--dry-run", is_flag=True, help="Print actions, do not write exclusion list.")
def main(decisions, cameras, apply, images_dir, labels_dir, exclude_list_out, dry_run):
    drops: dict[str, list[tuple[Path, Path, int]]] = {}

    for cam in cameras:
        for img_path in sorted((images_dir / str(cam)).glob("*.jpg")):
            label_path = labels_dir / str(cam) / (img_path.stem + ".txt")
            drop_reasons = []

            if apply in ("pre-specified", "both") and cam == 2:
                # cam_2-specific curation per session 2026-05-13 decision.
                # Other cameras are not modified — Arseniy chose to fix
                # cam_2 only for this iteration.
                if in_renovation_window(img_path.stem):
                    drop_reasons.append("renovation_window")
                bins_low = bins_below_half_mean(label_path, cam)
                if bins_low is not None:
                    drop_reasons.append(f"bins_below_half_mean__{bins_low}_bins")

            for reason in drop_reasons:
                drops.setdefault(f"{reason}__cam_{cam}", []).append(
                    (img_path, label_path, cam)
                )

    if apply in ("manual", "both") and decisions:
        with open(decisions, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["action"] in ("drop", "relabel"):
                    cam_match = None
                    for cam in cameras:
                        candidate = images_dir / str(cam) / row["filename"]
                        if candidate.exists():
                            cam_match = cam
                            break
                    if cam_match is None:
                        continue
                    img_path = images_dir / str(cam_match) / row["filename"]
                    label_path = labels_dir / str(cam_match) / (
                        Path(row["filename"]).stem + ".txt"
                    )
                    drops.setdefault(f"manual_{row['action']}__cam_{cam_match}", []).append(
                        (img_path, label_path, cam_match)
                    )

    # Report
    total = 0
    click.echo(f"\n{'reason':<40} {'count':>6}")
    click.echo("-" * 50)
    for reason, items in sorted(drops.items()):
        click.echo(f"{reason:<40} {len(items):>6}")
        total += len(items)
    click.echo("-" * 50)
    click.echo(f"{'TOTAL':<40} {total:>6}")

    # Collect unique filenames per camera to drop
    by_cam: dict[int, set[str]] = {}
    for reason, items in drops.items():
        for img_path, label_path, cam in items:
            by_cam.setdefault(cam, set()).add(img_path.name)

    if dry_run:
        click.echo("\n[dry-run] No exclusion list written.")
        return

    # Write per-camera exclusion lists
    for cam, fileset in by_cam.items():
        out_path = exclude_list_out.with_name(f"cam_{cam}_excluded.txt")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(sorted(fileset)) + "\n")
        click.echo(f"✓ cam_{cam}: {len(fileset)} unique filenames → {out_path}")

    click.echo("\nNo files moved. prepare_loso_fold.py will skip listed filenames.")


if __name__ == "__main__":
    main()
