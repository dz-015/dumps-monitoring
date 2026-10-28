"""Compute per-class instance counts after labeling N frames; project to full dataset.

Used at the 200-frame gate (plan v1.4 §3.5):
    if any class projects to <100 instances at the full target → escalate.
    Specifically for ground_trash, gate is <30 instances → activate Autodistill in parallel.

Run from repo root after exporting CVAT labels:

    ./ml/venv/bin/python ml/scripts/class_distribution.py \\
        --labels-dir ml/data/processed/labeled \\
        --total-target 1500
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import click

CLASS_NAMES = ["bin_ok", "bin_overflow", "ground_trash"]
GATE_DEFAULT = {"bin_ok": 100, "bin_overflow": 100, "ground_trash": 30}


def count_instances(labels_dir: Path) -> tuple[int, Counter]:
    """Walk YOLO-format .txt label files; return (frame_count, per-class instance counter)."""
    counts: Counter = Counter()
    n_frames = 0
    for label_file in labels_dir.rglob("*.txt"):
        n_frames += 1
        for line in label_file.read_text().splitlines():
            parts = line.strip().split()
            if not parts or len(parts) < 5:
                continue
            try:
                class_idx = int(parts[0])
            except ValueError:
                continue
            if 0 <= class_idx < len(CLASS_NAMES):
                counts[CLASS_NAMES[class_idx]] += 1
    return n_frames, counts


@click.command()
@click.option(
    "--labels-dir",
    type=click.Path(path_type=Path, exists=True, file_okay=False),
    required=True,
    help="Directory with YOLO-format .txt label files (one per frame).",
)
@click.option("--total-target", type=int, default=1500, help="Final target frame count.")
@click.option(
    "--gate-bin-ok", type=int, default=GATE_DEFAULT["bin_ok"], help="Min instances for bin_ok at full target."
)
@click.option(
    "--gate-bin-overflow",
    type=int,
    default=GATE_DEFAULT["bin_overflow"],
    help="Min instances for bin_overflow at full target.",
)
@click.option(
    "--gate-ground-trash",
    type=int,
    default=GATE_DEFAULT["ground_trash"],
    help="Min instances for ground_trash at full target (gate triggers Autodistill).",
)
def main(
    labels_dir: Path,
    total_target: int,
    gate_bin_ok: int,
    gate_bin_overflow: int,
    gate_ground_trash: int,
) -> None:
    n_frames, counts = count_instances(labels_dir)
    if n_frames == 0:
        raise click.ClickException(f"No label files found under {labels_dir}")

    gates = {
        "bin_ok": gate_bin_ok,
        "bin_overflow": gate_bin_overflow,
        "ground_trash": gate_ground_trash,
    }

    click.echo(f"Labeled frames so far: {n_frames}")
    click.echo(f"Final target:          {total_target}")
    click.echo(f"Scaling factor:        {total_target / n_frames:.2f}×")
    click.echo()
    click.echo(f"{'class':<14} {'observed':>10} {'projected':>11} {'gate':>6} {'status':>10}")
    click.echo("-" * 60)

    triggered: list[str] = []
    for cls in CLASS_NAMES:
        observed = counts[cls]
        projected = int(round(observed * total_target / n_frames))
        gate = gates[cls]
        status = "OK" if projected >= gate else "TRIGGER"
        if status == "TRIGGER":
            triggered.append(cls)
        click.echo(
            f"{cls:<14} {observed:>10} {projected:>11} {gate:>6} {status:>10}"
        )

    click.echo()
    if triggered:
        click.secho(f"Gate TRIGGERED for: {', '.join(triggered)}", fg="red")
        if "ground_trash" in triggered:
            click.echo("→ activate Autodistill+SAM2 parallel pipeline for ground_trash; do NOT pause labeling")
        if "bin_overflow" in triggered:
            click.echo("→ check labeling rule (inclusive); consider Q5 contingency Option F (in-domain copy-paste)")
        if "bin_ok" in triggered:
            click.echo("→ unexpected — bin_ok should always saturate first; check label format / class indexing")
        raise SystemExit(2)
    else:
        click.secho("All gates passed.", fg="green")


if __name__ == "__main__":
    main()
