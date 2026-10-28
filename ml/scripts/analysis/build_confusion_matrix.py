"""Aggregate confusion matrices across all best.pt of a config.

For each (config, fold), runs validation on best.pt, captures Ultralytics'
confusion matrix (3-class plus background bin), aggregates across seeds.
Outputs a per-fold confusion matrix + LOSO-aggregated.

Usage:
    python build_confusion_matrix.py \\
        --runs-root runs/detect/runs/level1 \\
        --folds-dir data/folds \\
        --out-dir runs/analysis/confusion
"""

from __future__ import annotations

import json
import os
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import click
import numpy as np


RUN_DIR_RE = re.compile(r"fold_(\d+)_seed_(\d+)$")
CAM_BY_FOLD = {0: "cam_1", 1: "cam_2", 2: "cam_3", 3: "cam_5", 4: "cam_7"}


def find_runs(runs_root: Path) -> list[tuple[str, int, int, Path]]:
    out = []
    for best_pt in runs_root.rglob("weights/best.pt"):
        run_dir = best_pt.parent.parent
        m = RUN_DIR_RE.search(run_dir.name)
        if not m:
            continue
        out.append((run_dir.parent.name, int(m.group(1)), int(m.group(2)), best_pt))
    return out


def get_confusion(weights: Path, data_yaml: Path, device: str = "0") -> np.ndarray | None:
    os.environ.setdefault("WANDB_MODE", "disabled")
    os.environ.setdefault("YOLO_VERBOSE", "False")
    from ultralytics import YOLO

    model = YOLO(str(weights))
    buf = StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        results = model.val(
            data=str(data_yaml),
            split="val",
            device=device,
            verbose=False,
            plots=True,  # required: Ultralytics 8.4 only fills cm.matrix when plots=True
            save_json=False,
        )
    cm = results.confusion_matrix
    if cm is None or not hasattr(cm, "matrix"):
        return None
    # cm.matrix shape: (nc+1, nc+1) — last row/col is background
    return cm.matrix.astype(int)


def render_table(matrix: np.ndarray, class_names: list[str]) -> str:
    n = matrix.shape[0]
    header = ["true\\pred"] + class_names + ["bg"][: n - len(class_names)]
    lines = ["  ".join(f"{h:<14}" for h in header)]
    for i, row in enumerate(matrix):
        label = class_names[i] if i < len(class_names) else "bg"
        cells = [f"{label:<14}"] + [f"{v:<14}" for v in row]
        lines.append("  ".join(cells))
    return "\n".join(lines)


@click.command()
@click.option("--runs-root", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--folds-dir", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--device", default="0")
@click.option("--out-dir", type=click.Path(path_type=Path), default=Path("runs/analysis/confusion"))
def main(runs_root: Path, folds_dir: Path, device: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    class_names = ["bin_ok", "bin_overflow", "ground_trash"]
    n_classes = len(class_names) + 1  # + background
    runs = find_runs(runs_root)
    if not runs:
        click.echo("No runs found")
        return
    click.echo(f"Processing {len(runs)} runs ...")

    by_config_fold: dict[str, dict[int, list[np.ndarray]]] = {}
    for config, fold, seed, best_pt in sorted(runs):
        data_yaml = folds_dir / f"fold_{fold}" / "data.yaml"
        if not data_yaml.exists():
            click.echo(f"  ✗ {config} fold={fold} seed={seed}: data.yaml missing")
            continue
        try:
            cm = get_confusion(best_pt, data_yaml, device=device)
        except Exception as e:
            click.echo(f"  ✗ {config} fold={fold} seed={seed}: {type(e).__name__}: {e}")
            continue
        if cm is None:
            click.echo(f"  ✗ {config} fold={fold} seed={seed}: no confusion matrix")
            continue
        click.echo(f"  ✓ {config} fold={fold} seed={seed}")
        by_config_fold.setdefault(config, {}).setdefault(fold, []).append(cm)

    out: dict = {}
    for config, fold_data in by_config_fold.items():
        config_out: dict = {"per_fold": {}, "loso_total": None, "per_fold_normalised": {}}
        loso_total = np.zeros((n_classes, n_classes), dtype=int)
        for fold, cms in fold_data.items():
            stacked = np.stack(cms, axis=0)
            mean_cm = stacked.mean(axis=0).astype(int)
            sum_cm = stacked.sum(axis=0)
            config_out["per_fold"][f"fold_{fold}_{CAM_BY_FOLD.get(fold)}"] = {
                "raw_per_seed": [cm.tolist() for cm in cms],
                "mean_across_seeds": mean_cm.tolist(),
                "sum_across_seeds": sum_cm.tolist(),
            }
            loso_total += sum_cm
        config_out["loso_total"] = loso_total.tolist()
        out[config] = config_out

        click.secho(f"\n=== {config} LOSO total confusion matrix (sum across folds × seeds) ===", fg="cyan")
        click.echo(render_table(loso_total, class_names))

    out_json = out_dir / f"{runs_root.name}_confusion.json"
    out_json.write_text(json.dumps(out, indent=2))
    click.echo(f"\nSaved: {out_json}")


if __name__ == "__main__":
    main()
