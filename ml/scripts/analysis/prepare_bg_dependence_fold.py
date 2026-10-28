"""Prepare a Background-Dependence ablation fold: train on ONE camera, test on others.

Per adversarial review v2: train cam_1 only, val on cam_2/3/5/7.
If F1 drops sharply on val, model learned camera-specific background, not bins.

This produces data/folds/bg_dep_train_<cam>/ symlinked dataset.

Usage:
    python prepare_bg_dependence_fold.py --train-cam 1 --val-cams 2 3 5 7
"""

from __future__ import annotations

from pathlib import Path

import click


def symlink_pair(src_img: Path, src_lbl: Path, dst_img: Path, dst_lbl: Path) -> int:
    n = 0
    for img in src_img.glob("*.jpg"):
        link_img = dst_img / img.name
        link_lbl = dst_lbl / (img.stem + ".txt")
        if link_img.exists():
            link_img.unlink()
        if link_lbl.exists():
            link_lbl.unlink()
        link_img.symlink_to(img.resolve())
        lbl = src_lbl / (img.stem + ".txt")
        if lbl.exists():
            link_lbl.symlink_to(lbl.resolve())
        else:
            link_lbl.write_text("")  # empty negative
        n += 1
    return n


@click.command()
@click.option("--train-cam", type=int, required=True)
@click.option("--val-cams", type=int, multiple=True, required=True)
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
    help="Default: data/folds/bg_dep_train_<cam>",
)
def main(
    train_cam: int,
    val_cams: tuple[int, ...],
    to_label_dir: Path,
    labeled_dir: Path,
    out_dir: Path | None,
) -> None:
    if out_dir is None:
        out_dir = Path(f"data/folds/bg_dep_train_{train_cam}")
    out_dir = Path(out_dir)

    train_img = out_dir / "images" / "train"
    train_lbl = out_dir / "labels" / "train"
    val_img = out_dir / "images" / "val"
    val_lbl = out_dir / "labels" / "val"
    for d in [train_img, train_lbl, val_img, val_lbl]:
        d.mkdir(parents=True, exist_ok=True)

    n_train = symlink_pair(
        to_label_dir / str(train_cam), labeled_dir / str(train_cam), train_img, train_lbl
    )
    click.echo(f"  train cam_{train_cam}: {n_train} images")

    n_val = 0
    for cam in val_cams:
        added = symlink_pair(
            to_label_dir / str(cam), labeled_dir / str(cam), val_img, val_lbl
        )
        click.echo(f"  val cam_{cam}: {added} images")
        n_val += added

    yaml_path = out_dir / "data.yaml"
    yaml_path.write_text(
        f"path: {out_dir.resolve()}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"names:\n  0: bin_ok\n  1: bin_overflow\n  2: ground_trash\n"
    )
    click.echo(f"\n✓ bg-dependence fold ready: {out_dir}")
    click.echo(f"  train: {n_train}  val: {n_val}  yaml: {yaml_path}")


if __name__ == "__main__":
    main()
