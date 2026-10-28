"""Scene-level aggregation over raw YOLO detections.

Given a trained model and a test split, produces the thesis's scene-level metrics:
- Recall(overflow), Precision(overflow), F1, PR-AUC
- Recall(contamination), Precision(contamination), F1, PR-AUC
- False-alarm-per-frame rate (overflow and contamination separately)
- Per-site F1 stability (std across LOSO folds)

Takes a directory of `fold_k/seed_s/best.pt` from a LOSO sweep, runs inference on
the held-out camera, aggregates to scene level, writes a single CSV of all numbers.
Scene-level thresholds are pinned at val-set F1-max (see review §5.2).
"""

from __future__ import annotations

from pathlib import Path

import click


@click.command()
@click.option("--runs-dir", type=click.Path(path_type=Path), required=True)
@click.option("--output", type=click.Path(path_type=Path), default=Path("ml/runs/scene_eval.csv"))
def main(runs_dir: Path, output: Path) -> None:
    """Aggregate all LOSO × seed runs under `runs_dir` into scene-level metrics."""
    # TODO(week3-fri): implement after first Level-1 run produces checkpoints.
    # Concrete steps:
    # 1. Glob runs_dir/fold_*/seed_*/weights/best.pt
    # 2. For each: load YOLO, run inference on fold's test camera, collect per-frame bboxes.
    # 3. Aggregate: scene = one frame; "overflow alert" = any bbox with class ending _overflow
    #    and confidence > threshold_overflow.
    # 4. Compute precision/recall/F1 against ground-truth scene labels.
    # 5. Write one CSV row per (fold, seed, metric).
    raise NotImplementedError(
        "Implement after Level-1 produces checkpoints in ml/runs/level1_baseline/."
    )


if __name__ == "__main__":
    main()
