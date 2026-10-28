"""Create CVAT IRR task for inter-rater reliability measurement.

Picks N random frames per camera (stratified) from `ml/data/processed/to_label/<cam>/`
and creates a NEW CVAT task with NO labels imported. A second annotator labels
this task independently. Cohen's κ is computed per class via bbox-IoU>0.5 matching
against Arseniy's labels (tasks 11-15) on the same source images.

Default: 30 frames × 5 cameras = 150 frames (~10% of 1498 dataset).

Run on 4090 host:
    python scripts/cvat_create_irr_task.py \\
        --cvat-url http://localhost:8080 \\
        --project-id 1 \\
        --frames-per-camera 30 \\
        --seed 42

The selection is saved to `data/processed/irr_selection.json` for later IRR analysis
(maps renamed filenames back to source camera + original filename).
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import click
import requests

from cvat_create_tasks import (
    create_task,
    list_existing_tasks,
    login,
    wait_for_data_processing,
)


def upload_data_with_rename(
    cvat_url: str,
    token: str,
    task_id: int,
    items: list[tuple[str, Path]],
    image_quality: int = 95,
) -> None:
    """Upload images with `cam<id>_` prefix to avoid filename collisions across cameras."""
    files = []
    for i, (cam, p) in enumerate(items):
        new_name = f"cam{cam}_{p.name}"
        files.append((f"client_files[{i}]", (new_name, p.read_bytes(), "image/jpeg")))

    data = {
        "image_quality": str(image_quality),
        "use_zip_chunks": "true",
        "use_cache": "true",
        "sorting_method": "lexicographical",
    }
    headers = {"Authorization": f"Token {token}"}
    r = requests.post(
        f"{cvat_url}/api/tasks/{task_id}/data",
        headers=headers,
        files=files,
        data=data,
        timeout=900,
    )
    r.raise_for_status()


@click.command()
@click.option("--cvat-url", default="http://localhost:8080")
@click.option("--project-id", type=int, required=True)
@click.option("--user", default="alex")
@click.option("--pass", "password", default="nekobak2026")
@click.option(
    "--to-label-dir",
    type=click.Path(path_type=Path, exists=True),
    default=Path("data/processed/to_label"),
)
@click.option("--cameras", default="1,2,3,5,7")
@click.option("--frames-per-camera", type=int, default=30)
@click.option("--task-name", default="cam_IRR")
@click.option("--seed", type=int, default=42)
@click.option(
    "--selection-out",
    type=click.Path(path_type=Path),
    default=Path("data/processed/irr_selection.json"),
)
def main(
    cvat_url: str,
    project_id: int,
    user: str,
    password: str,
    to_label_dir: Path,
    cameras: str,
    frames_per_camera: int,
    task_name: str,
    seed: int,
    selection_out: Path,
) -> None:
    cams = [c.strip() for c in cameras.split(",") if c.strip()]
    rng = random.Random(seed)

    selected: list[tuple[str, Path]] = []
    for cam in cams:
        cam_dir = to_label_dir / cam
        if not cam_dir.exists():
            click.secho(f"  [{cam}] directory missing, skipping", fg="yellow")
            continue
        frames = sorted(cam_dir.glob("*.jpg"))
        if len(frames) < frames_per_camera:
            click.secho(
                f"  [{cam}] only {len(frames)} frames, need {frames_per_camera}",
                fg="red",
            )
            raise SystemExit(1)
        sample = rng.sample(frames, frames_per_camera)
        sample.sort()
        selected.extend((cam, f) for f in sample)
        click.echo(f"  [{cam}] selected {len(sample)} frames")

    total = len(selected)
    click.echo(f"\nTotal: {total} frames for IRR task '{task_name}' (seed={seed})")

    selection_out.parent.mkdir(parents=True, exist_ok=True)
    selection_out.write_text(
        json.dumps(
            {
                "seed": seed,
                "frames_per_camera": frames_per_camera,
                "task_name": task_name,
                "items": [
                    {
                        "camera": cam,
                        "filename": p.name,
                        "renamed": f"cam{cam}_{p.name}",
                        "source_path": str(p),
                    }
                    for cam, p in selected
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    click.secho(f"Selection metadata: {selection_out}", fg="green")

    token = login(cvat_url, user, password)
    existing = list_existing_tasks(cvat_url, token, project_id)
    if task_name in existing:
        click.secho(
            f"Task '{task_name}' already exists (id={existing[task_name]}). "
            "Delete it via UI/API first if you want to recreate.",
            fg="red",
        )
        raise SystemExit(1)

    click.echo(f"\nCreating task '{task_name}'...")
    task_id = create_task(cvat_url, token, project_id, task_name)
    click.echo(f"  task_id={task_id}, uploading {total} images...")
    upload_data_with_rename(cvat_url, token, task_id, selected)
    state = wait_for_data_processing(cvat_url, token, task_id, timeout=900)
    click.secho(
        f"  state: {state} — open: {cvat_url}/tasks/{task_id}",
        fg="green" if state == "Finished" else "yellow",
    )

    if state == "Finished":
        click.echo("\n✓ IRR task ready. Share with second annotator:")
        click.echo(f"  URL: {cvat_url}/tasks/{task_id}")
        click.echo(f"  Login: {user} / <password>")
        click.echo(f"  Task name: {task_name}")
        click.echo("  Instructions: docs/labeling_instructions_for_irr.md")


if __name__ == "__main__":
    main()
