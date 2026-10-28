"""Explore the raw archive before sampling — sanity checks, not production.

Reads all image files under ml/data/raw/<camera_id>/, collects:
- resolution distribution
- file size distribution
- timestamp distribution per camera
- black-frame / single-colour detection (broken camera)

Writes ml/data/raw_audit.md with the findings. Safe to run many times.

Status: skeleton. Fill `collect_stats()` after we see actual directory layout.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click


@click.command()
@click.option("--raw-dir", type=click.Path(path_type=Path), default=Path("ml/data/raw"))
@click.option("--report", type=click.Path(path_type=Path), default=Path("ml/data/raw_audit.md"))
def main(raw_dir: Path, report: Path) -> None:
    """Audit the raw archive and write a human-readable report."""
    if not raw_dir.exists():
        click.secho(f"raw_dir does not exist: {raw_dir}", fg="red")
        sys.exit(1)
    # TODO(week3-mon): inspect first directory and decide schema. Expected layout:
    #   ml/data/raw/<camera_id>/YYYY-MM-DD/HH-MM.jpg
    # but the archive may use a different convention.
    raise NotImplementedError(
        "Populate after the archive is pulled. Need to see the directory layout first."
    )


if __name__ == "__main__":
    main()
