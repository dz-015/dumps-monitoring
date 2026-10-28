"""Prepare time-aligned LOSO fold using only frames from a chosen month range.

Per adversarial review v2 acceptance: cam_1/2/3 cover Feb-Apr, cam_5/7 only Apr.
This biases LOSO — folds where cam_1/2/3 land in test expose model to winter
conditions never seen in training.

This script filters frames by date prefix (YYYY-MM) and produces an Apr-only
fold structure for direct comparison with the full-history fold.

Usage:
    python prepare_time_aligned_subset.py \\
        --fold 0 \\
        --months 2026-04 \\
        --out-dir data/folds/fold_0_apr_only
"""

from __future__ import annotations

import re
from pathlib import Path

import click


WORKING_CAMERAS = [1, 2, 3, 5, 7]
DATE_FROM_STEM_RE = re.compile(r"^(\d{4}-\d{2})")


def filter_by_months(src_img_dir: Path, months: set[str]) -> list[Path]:
    """Return jpgs whose stem starts with one of the YYYY-MM in `months`."""
    out = []
    for img in sorted(src_img_dir.glob("*.jpg")):
        m = DATE_FROM_STEM_RE.match(img.stem)
        if not m:
            continue
        if m.group(1) in months:
            out.append(img)
    return out


def symlink_pair(
    images: list[Path], src_lbl_dir: Path, dst_img: Path, dst_lbl: Path
) -> int:
    n = 0
    for img in images:
        link_img = dst_img / img.name
        link_lbl = dst_lbl / (img.stem + ".txt")
        if link_img.exists():
            link_img.unlink()
        if link_lbl.exists():
            link_lbl.unlink()
        link_img.symlink_to(img.resolve())
        lbl = src_lbl_dir / (img.stem + ".txt")
        if lbl.exists():
            link_lbl.symlink_to(lbl.resolve())
        else:
            link_lbl.write_text("")
        n += 1
    return n


@click.command()
@click.option("--fold", type=int, required=True, help="LOSO fold index 0..4")
@click.option(
    "--months",
    multiple=True,
    required=True,
    help="One or more YYYY-MM values to keep (e.g. --months 2026-04).",
)
@click.option(
    "--to-label-dir",
    type=click.Path(path_type=Path, exists=True),
    default=Path("data/processed/to_label"),
)
@click.option(
    "--labeled-dir",
    type=click.Path(path_type=Path, exists=True),
    default=Path("data/processed/labeled"),
)
@click.option(
    "--out-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Default: data/folds/fold_<fold>_<months_joined>",
)
def main(
    fold: int,
    months: tuple[str, ...],
    to_label_dir: Path,
    labeled_dir: Path,
    out_dir: Path | None,
) -> None:
    months_set = set(months)
    test_cam = WORKING_CAMERAS[fold]
    train_cams = [c for c in WORKING_CAMERAS if c != test_cam]

    if out_dir is None:
        joined = "_".join(sorted(months_set)).replace("-", "")
        out_dir = Path(f"data/folds/fold_{fold}_{joined}")
    out_dir = Path(out_dir)

    train_img = out_dir / "images" / "train"
    train_lbl = out_dir / "labels" / "train"
    val_img = out_dir / "images" / "val"
    val_lbl = out_dir / "labels" / "val"
    for d in [train_img, train_lbl, val_img, val_lbl]:
        d.mkdir(parents=True, exist_ok=True)

    click.echo(f"Time-aligned fold {fold}: test=cam_{test_cam}, train={train_cams}")
    click.echo(f"Months kept: {sorted(months_set)}")

    n_train = 0
    for cam in train_cams:
        cam_imgs = filter_by_months(to_label_dir / str(cam), months_set)
        added = symlink_pair(cam_imgs, labeled_dir / str(cam), train_img, train_lbl)
        click.echo(f"  train cam_{cam}: {added} images (after time filter)")
        n_train += added

    test_imgs = filter_by_months(to_label_dir / str(test_cam), months_set)
    n_val = symlink_pair(test_imgs, labeled_dir / str(test_cam), val_img, val_lbl)
    click.echo(f"  val cam_{test_cam}: {n_val} images (after time filter)")

    yaml_path = out_dir / "data.yaml"
    yaml_path.write_text(
        f"path: {out_dir.resolve()}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"names:\n  0: bin_ok\n  1: bin_overflow\n  2: ground_trash\n"
    )
    click.echo(f"\n✓ time-aligned fold ready: {out_dir}")
    click.echo(f"  train: {n_train}  val: {n_val}  yaml: {yaml_path}")
    if n_train < 100 or n_val < 30:
        click.secho(
            f"  ⚠ small subset: train={n_train}, val={n_val}. "
            f"Filter may be too restrictive.",
            fg="yellow",
        )


if __name__ == "__main__":
    main()
