"""Drive a full LOSO × seed matrix for a given config.

    python -m ml.scripts.run_loso --config ml/configs/level1.yaml

K-fold LOSO where K = number of working cameras after audit.
Runs train_detection.py as a subprocess so failures are isolated per run.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click
import yaml

MIN_FOLDS = 3  # below K=3, LOSO mean ± std becomes statistical fiction


@click.command()
@click.option("--config", type=click.Path(path_type=Path, exists=True), required=True)
@click.option(
    "--dry-run", is_flag=True, help="Print commands without executing. Useful before overnight runs."
)
def main(config: Path, dry_run: bool) -> None:
    cfg = yaml.safe_load(config.read_text())
    ev = cfg["evaluation"]
    if ev["num_folds"] is None:
        raise click.ClickException(
            "evaluation.num_folds is None. Set it to the number of working cameras after audit. "
            "If K<3, abandon LOSO and document as Limitation."
        )
    if ev["num_folds"] < MIN_FOLDS:
        raise click.ClickException(
            f"K={ev['num_folds']} folds is too few; minimum is {MIN_FOLDS}. "
            "Pivot to single-camera train/val/test by date and document as Limitation."
        )
    folds = range(ev["num_folds"])
    seeds = ev["seeds"]

    total = len(folds) * len(seeds)
    click.echo(f"Running {total} trainings: {len(folds)} folds × {len(seeds)} seeds")

    for fold in folds:
        for seed in seeds:
            cmd = [
                sys.executable,
                "-m",
                "ml.scripts.train_detection",
                "--config",
                str(config),
                "--fold",
                str(fold),
                "--seed",
                str(seed),
            ]
            click.echo(f"  fold={fold} seed={seed}: {' '.join(cmd)}")
            if not dry_run:
                result = subprocess.run(cmd, check=False)
                if result.returncode != 0:
                    click.secho(f"  ✗ fold={fold} seed={seed} failed", fg="red")
                    # Continue to next — one failed run shouldn't kill the whole sweep.
                else:
                    click.secho(f"  ✓ fold={fold} seed={seed} done", fg="green")


if __name__ == "__main__":
    main()
