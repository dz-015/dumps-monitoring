"""Class-imbalance helpers for YOLOv8.

Two approaches, cheapest-first:
1. `class_weights` on BCE — built into Ultralytics but not exposed on CLI; set via model attr.
2. Weighted sampler — not built into Ultralytics; monkey-patch pattern from y-t-g.github.io.

Reference for approach 2: https://y-t-g.github.io/tutorials/yolo-class-balancing/
Reported gain on a traffic-light-like rare class: +6.6 mAP@0.5.
"""

from __future__ import annotations

from collections import Counter


def compute_inverse_frequency_weights(
    instance_counts: dict[str, int],
    class_order: list[str],
    smoothing: float = 1.0,
) -> list[float]:
    """Inverse-frequency class weights, normalised so mean = 1.0.

    smoothing: add to each count before inversion to avoid exploding weights
    on tiny classes. 1.0 is conservative; 0.0 is pure inverse-frequency.
    """
    counts = [instance_counts.get(c, 0) + smoothing for c in class_order]
    if any(n == 0 for n in counts):
        raise ValueError(f"Zero count for some class even after smoothing: {counts}")
    inv = [1.0 / n for n in counts]
    mean_inv = sum(inv) / len(inv)
    return [w / mean_inv for w in inv]


def count_instances_per_class(label_files: list[str], n_classes: int) -> Counter[int]:
    """Count class IDs across YOLO-format .txt label files.

    Each line: `class_id cx cy w h` (normalised).
    """
    counter: Counter[int] = Counter()
    for f in label_files:
        with open(f) as fh:
            for line in fh:
                parts = line.strip().split()
                if not parts:
                    continue
                cls = int(parts[0])
                if 0 <= cls < n_classes:
                    counter[cls] += 1
    return counter


# TODO(week3): the model-attribute patch snippet for Ultralytics goes here.
# It's ~5 lines but requires a live Ultralytics model to test, so we stub.
