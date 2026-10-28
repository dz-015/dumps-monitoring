"""Generate fold-specific data.yaml + symlinked image/label dirs for K-fold LOSO.

For each fold `k` (test camera = working_cameras[k]):
  - data/folds/fold_<k>/images/train/   ← symlinks to all cams except test
  - data/folds/fold_<k>/images/val/     ← symlinks to test camera
  - data/folds/fold_<k>/labels/train/   ← parallel symlinks to YOLO .txt
  - data/folds/fold_<k>/labels/val/
  - data/folds/fold_<k>/data.yaml       ← Ultralytics dataset YAML

Filenames are prefixed `cam<N>_` to avoid collisions across cameras.

Usage:
    python scripts/prepare_loso_fold.py --fold 0
    python scripts/prepare_loso_fold.py --config configs/level1.yaml --fold 2
"""

from __future__ import annotations

import os
from pathlib import Path

import click
import yaml


def _load_exclusion(excluded_root: Path | None, cam: str) -> set[str]:
    """Read cam_<X>_excluded.txt with one filename per line, if present."""
    if excluded_root is None:
        return set()
    f = excluded_root / f"cam_{cam}_excluded.txt"
    if not f.exists():
        return set()
    return {line.strip() for line in f.read_text().splitlines() if line.strip()}


def _symlink_camera(
    src_img_dir: Path,
    src_lbl_dir: Path,
    dst_img_dir: Path,
    dst_lbl_dir: Path,
    cam: str,
    excluded: set[str] | None = None,
) -> tuple[int, int]:
    """Create cam-prefixed symlinks. Returns (img_count, lbl_count)."""
    dst_img_dir.mkdir(parents=True, exist_ok=True)
    dst_lbl_dir.mkdir(parents=True, exist_ok=True)

    excluded = excluded or set()
    img_count = 0
    lbl_count = 0

    for img in src_img_dir.glob("*.jpg"):
        if img.name in excluded:
            continue
        link_name = dst_img_dir / f"cam{cam}_{img.name}"
        if link_name.exists() or link_name.is_symlink():
            link_name.unlink()
        link_name.symlink_to(img.resolve())
        img_count += 1

        # parallel label (same stem, .txt extension); may not exist for empty frames
        lbl = src_lbl_dir / f"{img.stem}.txt"
        lbl_link = dst_lbl_dir / f"cam{cam}_{img.stem}.txt"
        if lbl_link.exists() or lbl_link.is_symlink():
            lbl_link.unlink()
        if lbl.exists():
            lbl_link.symlink_to(lbl.resolve())
            lbl_count += 1
        else:
            # YOLO treats missing label file as empty (no objects). Create empty file
            # so Ultralytics recognizes the image as a labeled negative.
            lbl_link.write_text("")

    return img_count, lbl_count


@click.command()
@click.option(
    "--config",
    type=click.Path(path_type=Path, exists=True),
    default=Path("configs/level1.yaml"),
)
@click.option("--fold", type=int, required=True, help="LOSO fold index 0..K-1")
@click.option(
    "--to-label-dir",
    type=click.Path(path_type=Path, exists=True),
    default=Path("data/processed/to_label"),
    help="Source image dirs (one subdir per camera)",
)
@click.option(
    "--labeled-dir",
    type=click.Path(path_type=Path, exists=True),
    default=Path("data/processed/labeled"),
    help="Source YOLO label dirs (one subdir per camera)",
)
@click.option(
    "--excluded-dir",
    type=click.Path(path_type=Path),
    default=Path("data/processed"),
    help="Directory containing cam_<X>_excluded.txt files (one filename per line).",
)
@click.option(
    "--folds-dir",
    type=click.Path(path_type=Path),
    default=Path("data/folds"),
)
@click.option(
    "--force",
    is_flag=True,
    help="Remove existing fold dir and recreate from scratch",
)
def main(
    config: Path,
    fold: int,
    to_label_dir: Path,
    labeled_dir: Path,
    excluded_dir: Path,
    folds_dir: Path,
    force: bool,
) -> None:
    cfg = yaml.safe_load(config.read_text())
    ev = cfg["evaluation"]
    working_cameras = [str(c) for c in ev["working_cameras"]]
    K = len(working_cameras)

    if fold < 0 or fold >= K:
        raise click.ClickException(f"fold={fold} out of range [0, {K})")

    test_cam = working_cameras[fold]
    train_cams = [c for c in working_cameras if c != test_cam]

    click.echo(f"Fold {fold}: test=cam_{test_cam}, train={train_cams}")

    fold_dir = folds_dir / f"fold_{fold}"
    if fold_dir.exists() and force:
        click.echo(f"  removing existing {fold_dir}")
        import shutil
        shutil.rmtree(fold_dir)

    img_train = fold_dir / "images" / "train"
    img_val = fold_dir / "images" / "val"
    lbl_train = fold_dir / "labels" / "train"
    lbl_val = fold_dir / "labels" / "val"

    # Train: all cams except test
    train_imgs = 0
    train_lbls = 0
    for cam in train_cams:
        src_img = to_label_dir / cam
        src_lbl = labeled_dir / cam
        if not src_img.exists():
            click.secho(f"  [train cam_{cam}] image dir missing: {src_img}", fg="red")
            raise SystemExit(1)
        if not src_lbl.exists():
            click.secho(f"  [train cam_{cam}] label dir missing: {src_lbl}", fg="red")
            raise SystemExit(1)
        excluded = _load_exclusion(excluded_dir, cam)
        if excluded:
            click.echo(f"  train cam_{cam}: excluding {len(excluded)} filenames via exclusion list")
        i, l = _symlink_camera(src_img, src_lbl, img_train, lbl_train, cam, excluded)
        train_imgs += i
        train_lbls += l
        click.echo(f"  train cam_{cam}: {i} images, {l} non-empty labels")

    # Val: test cam
    src_img = to_label_dir / test_cam
    src_lbl = labeled_dir / test_cam
    excluded = _load_exclusion(excluded_dir, test_cam)
    if excluded:
        click.echo(f"  val cam_{test_cam}: excluding {len(excluded)} filenames via exclusion list")
    val_imgs, val_lbls = _symlink_camera(src_img, src_lbl, img_val, lbl_val, test_cam, excluded)
    click.echo(f"  val cam_{test_cam}: {val_imgs} images, {val_lbls} non-empty labels")

    # Generate data.yaml
    nc = 3
    names = ["bin_ok", "bin_overflow", "ground_trash"]
    data_yaml = {
        "path": str(fold_dir.resolve()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/val",  # same as val for now; LOSO doesn't have separate test
        "nc": nc,
        "names": {i: n for i, n in enumerate(names)},
    }
    data_yaml_path = fold_dir / "data.yaml"
    data_yaml_path.write_text(yaml.safe_dump(data_yaml, sort_keys=False))

    click.secho(
        f"\n✓ fold {fold} ready: {fold_dir}\n"
        f"  train: {train_imgs} images ({train_lbls} non-empty)\n"
        f"  val:   {val_imgs} images ({val_lbls} non-empty)\n"
        f"  yaml:  {data_yaml_path}",
        fg="green",
    )


if __name__ == "__main__":
    main()
