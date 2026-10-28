"""Train detector with custom Albumentations augmentation pipeline.

Wraps the standard train_detection.py logic and injects an Albumentations
pipeline via Ultralytics' `augmentations=` train() argument (2025 API).

Pipeline name (e.g. nightaug_cctv) is selected by --aug-pipeline.

Usage:
    python scripts/train_detection_aug.py \\
        --config configs/yolov8m_nightaug.yaml \\
        --fold 1 --seed 0 \\
        --aug-pipeline nightaug_cctv \\
        --runs-root runs/aug_test \\
        --no-wandb
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import click
import yaml


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


def _ensure_fold(fold: int, config_path: Path, folds_dir: Path) -> Path:
    fold_dir = folds_dir / f"fold_{fold}"
    yaml_path = fold_dir / "data.yaml"
    if yaml_path.exists():
        return yaml_path
    raise FileNotFoundError(
        f"Fold {fold} not prepared; run prepare_loso_fold.py first ({yaml_path} missing)"
    )


@click.command()
@click.option("--config", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--fold", type=int, default=0)
@click.option("--seed", type=int, default=0)
@click.option("--folds-dir", type=click.Path(path_type=Path), default=Path("data/folds"))
@click.option("--runs-root", type=click.Path(path_type=Path), default=Path("runs"))
@click.option("--freeze", type=int, default=None)
@click.option("--device", default="0")
@click.option("--wandb-project", default="nekobak")
@click.option("--no-wandb", is_flag=True)
@click.option(
    "--aug-pipeline",
    type=click.Choice(["nightaug_cctv", "nightaug_color_only", "cam7_glare", "default"]),
    default="default",
    help="Albumentations pipeline name from src/training/nightaug_pipeline.py "
    "or 'default' to fall back to Ultralytics built-in.",
)
def main(
    config: Path,
    fold: int,
    seed: int,
    folds_dir: Path,
    runs_root: Path,
    freeze: int | None,
    device: str,
    wandb_project: str,
    no_wandb: bool,
    aug_pipeline: str,
) -> None:
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    if no_wandb:
        os.environ["WANDB_MODE"] = "disabled"

    import torch  # noqa

    cfg = yaml.safe_load(config.read_text())
    cfg["train"]["seed"] = seed
    exp_name = cfg["experiment"]["name"]

    fold_data_yaml = _ensure_fold(fold, config, folds_dir)

    run_name = f"fold_{fold}_seed_{seed}"
    if freeze is not None:
        run_name += f"_freeze_{freeze}"
    if aug_pipeline != "default":
        run_name += f"_aug_{aug_pipeline}"

    sha = _git_sha()
    click.echo(f"=== {exp_name} / {run_name} (git {sha}) ===")
    click.echo(f"  config: {config}")
    click.echo(f"  data:   {fold_data_yaml}")
    click.echo(f"  aug:    {aug_pipeline}")
    click.echo(
        f"  cuda:   {torch.cuda.is_available()} "
        f"({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu'})"
    )

    from ultralytics import YOLO  # noqa: E402

    arch = cfg["model"]["arch"]
    model = YOLO(arch)

    t = cfg["train"]
    a = cfg.get("augmentation", {})
    train_kwargs: dict = {
        "data": str(fold_data_yaml),
        "epochs": t["epochs"],
        "patience": t["patience"],
        "batch": t["batch"],
        "imgsz": t["imgsz"],
        "lr0": t["lr0"],
        "lrf": t["lrf"],
        "cos_lr": t["cos_lr"],
        "warmup_epochs": t["warmup_epochs"],
        "close_mosaic": t["close_mosaic"],
        "seed": seed,
        "deterministic": t["deterministic"],
        "cache": t["cache"],
        "workers": t["workers"],
        "device": device,
        "project": str(runs_root),
        "name": f"{exp_name}/{run_name}",
        "exist_ok": True,
        # augmentation hyperparameters (Ultralytics built-in)
        "hsv_h": a.get("hsv_h", 0.015),
        "hsv_s": a.get("hsv_s", 0.7),
        "hsv_v": a.get("hsv_v", 0.4),
        "translate": a.get("translate", 0.1),
        "scale": a.get("scale", 0.5),
        "mosaic": a.get("mosaic", 1.0),
        "fliplr": a.get("fliplr", 0.0),
        "flipud": a.get("flipud", 0.0),
        "mixup": a.get("mixup", 0.0),
        "copy_paste": a.get("copy_paste", 0.0),
    }
    if freeze is not None:
        train_kwargs["freeze"] = freeze

    # Inject custom Albumentations pipeline
    if aug_pipeline != "default":
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from training.nightaug_pipeline import get_pipeline  # noqa: E402

        compose = get_pipeline(aug_pipeline, imgsz=t["imgsz"])
        click.echo(f"  Injected augmentations: {len(compose.transforms)} transforms")
        # Ultralytics 8.4.x: pass via augmentations= (2025 API)
        # Fallback: monkey-patch the dataset's albumentations attribute
        train_kwargs["augmentations"] = compose

    if not no_wandb:
        os.environ["WANDB_PROJECT"] = wandb_project

    results = model.train(**train_kwargs)

    weights_path = Path(results.save_dir) / "weights" / "best.pt"
    click.echo(f"\n✓ done — best.pt at {weights_path}")
    if hasattr(results, "results_dict"):
        rd = results.results_dict
        for k in ["metrics/mAP50(B)", "metrics/mAP50-95(B)"]:
            if k in rd:
                click.echo(f"  {k}: {rd[k]:.4f}")


if __name__ == "__main__":
    main()
