"""Train a YOLOv8 detector for one LOSO fold + one seed.

    python scripts/train_detection.py --config configs/level1.yaml --fold 0 --seed 0

One invocation = one training run. Runs under control of `run_loso.py` for the K-fold × seed matrix.

Pipeline:
  1. Load config YAML
  2. Ensure fold dir exists (subprocess `prepare_loso_fold.py` if missing)
  3. Set deterministic env vars before torch import
  4. Instantiate YOLO model from cfg.model.arch
  5. Call model.train() with hyperparams from cfg.train + cfg.augmentation
  6. W&B auto-logs if installed and not --no-wandb
  7. best.pt saved to runs/<exp>/fold_<fold>/seed_<seed>/weights/
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
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def _ultralytics_kwargs(cfg: dict, fold_data_yaml: Path) -> dict:
    """Translate our internal schema to Ultralytics YOLO.train() kwargs."""
    t = cfg["train"]
    a = cfg["augmentation"]
    kwargs_ = {
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
        "seed": t["seed"],
        "deterministic": t["deterministic"],
        "cache": t["cache"],
        "workers": t["workers"],
        # Augmentation
        "hsv_h": a["hsv_h"],
        "hsv_s": a["hsv_s"],
        "hsv_v": a["hsv_v"],
        "translate": a["translate"],
        "scale": a["scale"],
        "mosaic": a["mosaic"],
        "fliplr": a["fliplr"],
        "flipud": a["flipud"],
        "degrees": a["degrees"],
        "shear": a["shear"],
        "perspective": a["perspective"],
        "mixup": a["mixup"],
        "copy_paste": a.get("copy_paste", 0.0),
    }
    for _o in ("optimizer", "amp", "rect", "weight_decay", "momentum", "warmup_momentum", "nbs"):
        if _o in t:
            kwargs_[_o] = t[_o]
    return kwargs_


def _ensure_fold(fold: int, config_path: Path, folds_dir: Path) -> Path:
    """Subprocess-call prepare_loso_fold.py if fold dir doesn't exist. Returns data.yaml path."""
    fold_dir = folds_dir / f"fold_{fold}"
    data_yaml = fold_dir / "data.yaml"
    if data_yaml.exists():
        return data_yaml

    click.echo(f"Fold {fold} not prepared yet — invoking prepare_loso_fold.py...")
    script_dir = Path(__file__).parent
    cmd = [
        sys.executable,
        str(script_dir / "prepare_loso_fold.py"),
        "--config",
        str(config_path),
        "--fold",
        str(fold),
        "--folds-dir",
        str(folds_dir),
    ]
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise click.ClickException(f"prepare_loso_fold.py failed for fold {fold}")
    if not data_yaml.exists():
        raise click.ClickException(f"prepare_loso_fold.py succeeded but data.yaml missing: {data_yaml}")
    return data_yaml


@click.command()
@click.option("--config", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--fold", type=int, default=0, help="LOSO fold index 0..K-1")
@click.option("--seed", type=int, default=0)
@click.option(
    "--folds-dir",
    type=click.Path(path_type=Path),
    default=Path("data/folds"),
)
@click.option(
    "--runs-root",
    type=click.Path(path_type=Path),
    default=Path("runs"),
)
@click.option(
    "--freeze",
    type=int,
    default=None,
    help="Optional freeze depth for per-site fine-tuning ablation",
)
@click.option("--device", type=str, default="0", help="GPU device index or 'cpu'")
@click.option("--wandb-project", default="nekobak")
@click.option("--no-wandb", is_flag=True, help="Disable W&B logging entirely")
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
) -> None:
    # Determinism env vars (must be set before torch import inside ultralytics)
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    if no_wandb:
        os.environ["WANDB_MODE"] = "disabled"

    import torch  # noqa: E402

    cfg = yaml.safe_load(config.read_text())
    cfg["train"]["seed"] = seed
    exp_name = cfg["experiment"]["name"]

    fold_data_yaml = _ensure_fold(fold, config, folds_dir)

    run_name = f"fold_{fold}_seed_{seed}"
    if freeze is not None:
        run_name += f"_freeze_{freeze}"

    sha = _git_sha()
    click.echo(f"=== {exp_name} / {run_name} (git {sha}) ===")
    click.echo(f"  config: {config}")
    click.echo(f"  data:   {fold_data_yaml}")
    click.echo(
        f"  cuda:   {torch.cuda.is_available()} "
        f"({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu'})"
    )

    arch = cfg["model"]["arch"]
    if "rtdetr" in arch.lower():
        from ultralytics import RTDETR
        model = RTDETR(arch)
    else:
        from ultralytics import YOLO
        model = YOLO(arch)

    if cfg["model"].get("class_weights") is not None:
        click.secho(
            "  WARNING: class_weights specified but not yet wired into Ultralytics. Ignored.",
            fg="yellow",
        )

    if not no_wandb:
        try:
            import wandb
            wandb.init(
                project=wandb_project,
                name=f"{exp_name}__{run_name}",
                config={**cfg, "fold": fold, "seed": seed, "git_sha": sha, "freeze": freeze},
                resume="allow",
            )
        except Exception as e:
            click.secho(f"  W&B init failed ({e}); continuing without logging", fg="yellow")

    kwargs = _ultralytics_kwargs(cfg, fold_data_yaml)
    kwargs["device"] = device
    kwargs["project"] = str(runs_root / exp_name)
    kwargs["name"] = run_name
    kwargs["exist_ok"] = True
    kwargs["plots"] = True
    kwargs["save"] = True
    if freeze is not None:
        kwargs["freeze"] = freeze

    click.echo("=== train kwargs ===")
    for k, v in kwargs.items():
        click.echo(f"  {k}: {v}")

    results = model.train(**kwargs)

    save_dir = Path(kwargs["project"]) / kwargs["name"]
    best_pt = save_dir / "weights" / "best.pt"
    click.secho(f"\n✓ done — best.pt at {best_pt}", fg="green")

    try:
        click.echo(f"  Best mAP50:    {results.box.map50:.4f}")
        click.echo(f"  Best mAP50-95: {results.box.map:.4f}")
    except Exception:
        pass


if __name__ == "__main__":
    main()
