"""LOSO fold assembly — build data.yaml per fold.

With N=3 cameras, LOSO produces 3 folds:
  fold 0: train=[A, B], test=[C]
  fold 1: train=[A, C], test=[B]
  fold 2: train=[B, C], test=[A]

Each fold writes a YOLO data.yaml and updates the train/val/test txt splits.
"""

from __future__ import annotations

from pathlib import Path


def build_fold(
    fold_idx: int,
    cameras: list[str],
    processed_dir: Path,
    out_dir: Path,
) -> Path:
    """Assemble a data.yaml for fold `fold_idx`. Returns path to the generated YAML."""
    # TODO(week3): once we have a processed set per camera, generate YOLO-format txt
    # files pointing at the image paths. Return a data.yaml with train/val/test entries
    # and the shared class list.
    raise NotImplementedError(
        "Wire once ml/data/processed/<camera>/ exists. Until then, fold assembly is moot."
    )


CLASSES_L1 = [
    "metal_ok",
    "metal_overflow",
    "plastic_ok",
    "plastic_overflow",
    "euro_ok",
    "euro_overflow",
    "ground_trash",
]

CLASSES_L0 = ["metal", "plastic", "euro"]
