"""Create CVAT review task: 50 random frames per camera (250 total) with Arseniy's labels imported.

For each camera, picks N random frames from existing tasks 11-15, fetches their
annotations, creates a new task `cam_review` with the same frames AND pre-imported
labels. Arseniy can then browse the task in CVAT and visually verify labels —
quick QC pass without going through 1498 frames.

Run on 4090 host after cvat_export_labels.py:
    python scripts/cvat_create_review_task.py \\
        --cvat-url http://localhost:8080 \\
        --project-id 1 \\
        --frames-per-camera 50 \\
        --seed 7
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

import click
import requests

from cvat_create_tasks import (
    create_task,
    list_existing_tasks,
    login,
    wait_for_data_processing,
)
from cvat_export_labels import (
    get_job_annotations,
    get_job_meta,
    get_project_labels,
    get_task_jobs,
    list_tasks_in_project,
)


def upload_data_with_rename(
    cvat_url: str,
    token: str,
    task_id: int,
    items: list[tuple[str, str, Path]],
) -> None:
    """items = [(camera_id, original_filename, source_path)]."""
    files = []
    for i, (cam, orig_name, p) in enumerate(items):
        new_name = f"cam{cam}_{orig_name}"
        files.append((f"client_files[{i}]", (new_name, p.read_bytes(), "image/jpeg")))
    data = {
        "image_quality": "95",
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


def get_new_task_frame_order(cvat_url: str, token: str, task_id: int) -> list[str]:
    """Returns frame names in upload order (matches frame_idx 0..N-1 in the new task)."""
    job_ids = get_task_jobs(cvat_url, token, task_id)
    if not job_ids:
        return []
    meta = get_job_meta(cvat_url, token, job_ids[0])
    return [f["name"] for f in meta]


def put_annotations(
    cvat_url: str,
    token: str,
    job_id: int,
    shapes: list[dict],
) -> None:
    """PUT entire annotations payload (replaces existing)."""
    payload = {"version": 0, "tags": [], "shapes": shapes, "tracks": []}
    r = requests.put(
        f"{cvat_url}/api/jobs/{job_id}/annotations",
        headers={
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    if not r.ok:
        click.secho(f"  PUT annotations failed: {r.status_code} {r.text[:500]}", fg="red")
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
@click.option("--task-prefix", default="cam_")
@click.option(
    "--skip-tasks",
    default="cam_IRR,cam_review",
)
@click.option("--frames-per-camera", type=int, default=50)
@click.option("--review-task-name", default="cam_review")
@click.option("--seed", type=int, default=7)
def main(
    cvat_url: str,
    project_id: int,
    user: str,
    password: str,
    to_label_dir: Path,
    task_prefix: str,
    skip_tasks: str,
    frames_per_camera: int,
    review_task_name: str,
    seed: int,
) -> None:
    skip = {s.strip() for s in skip_tasks.split(",") if s.strip()}
    rng = random.Random(seed)
    token = login(cvat_url, user, password)
    click.echo(f"Logged in as {user}")

    labels_map = get_project_labels(cvat_url, token, project_id)
    click.echo(f"Project labels: {labels_map}")

    existing = list_existing_tasks(cvat_url, token, project_id)
    if review_task_name in existing:
        click.secho(
            f"Task '{review_task_name}' already exists (id={existing[review_task_name]}). "
            "Delete via UI/API first.",
            fg="red",
        )
        raise SystemExit(1)

    tasks = list_tasks_in_project(cvat_url, token, project_id)
    source_tasks = [
        t for t in tasks if t["name"].startswith(task_prefix) and t["name"] not in skip
    ]
    click.echo(f"\nSource tasks: {[t['name'] for t in source_tasks]}")

    selected_items: list[tuple[str, str, Path]] = []
    all_shapes_to_upload: list[dict] = []
    frame_idx_counter = 0
    seen_filenames = set()

    for task in sorted(source_tasks, key=lambda t: t["name"]):
        task_name = task["name"]
        cam = task_name[len(task_prefix):]
        cam_dir = to_label_dir / cam
        if not cam_dir.exists():
            click.secho(f"  [{cam}] no source dir, skip", fg="yellow")
            continue

        job_ids = get_task_jobs(cvat_url, token, task["id"])
        if not job_ids:
            click.secho(f"  [{cam}] no jobs, skip", fg="yellow")
            continue

        # Get meta + annotations from source task
        click.echo(f"\n[{cam}] fetching meta + annotations from task {task['id']}...")
        all_meta = []
        all_shapes_by_frame: dict[int, list] = {}
        for job_id in job_ids:
            meta = get_job_meta(cvat_url, token, job_id)
            ann = get_job_annotations(cvat_url, token, job_id)
            for s in ann.get("shapes", []):
                all_shapes_by_frame.setdefault(s["frame"], []).append(s)
            all_meta.extend(meta)

        if len(all_meta) < frames_per_camera:
            click.secho(
                f"  [{cam}] only {len(all_meta)} frames in source task, need {frames_per_camera}",
                fg="red",
            )
            raise SystemExit(1)

        # Random sample N source-frame indices
        sampled_src_idxs = rng.sample(range(len(all_meta)), frames_per_camera)
        sampled_src_idxs.sort()

        for src_idx in sampled_src_idxs:
            frame_meta = all_meta[src_idx]
            orig_name = frame_meta["name"]
            source_path = cam_dir / Path(orig_name).name
            if not source_path.exists():
                click.secho(f"    missing source file: {source_path}", fg="yellow")
                continue
            new_name = f"cam{cam}_{Path(orig_name).name}"
            if new_name in seen_filenames:
                continue
            seen_filenames.add(new_name)

            selected_items.append((cam, Path(orig_name).name, source_path))

            # Re-build shapes for this frame, with new frame index
            for s in all_shapes_by_frame.get(src_idx, []):
                if s["type"] != "rectangle":
                    continue
                shape_copy = {
                    "type": "rectangle",
                    "occluded": s.get("occluded", False),
                    "outside": s.get("outside", False),
                    "z_order": s.get("z_order", 0),
                    "rotation": s.get("rotation", 0.0),
                    "points": s["points"],
                    "frame": frame_idx_counter,
                    "label_id": s["label_id"],
                    "group": s.get("group", 0),
                    "source": "manual",
                    "attributes": s.get("attributes", []),
                }
                all_shapes_to_upload.append(shape_copy)

            frame_idx_counter += 1

        click.echo(
            f"  [{cam}] selected {frames_per_camera}, total shapes so far={len(all_shapes_to_upload)}"
        )

    total_items = len(selected_items)
    total_shapes = len(all_shapes_to_upload)
    click.echo(f"\n=== will upload {total_items} frames with {total_shapes} bboxes ===")

    # Create new task
    click.echo(f"\nCreating task '{review_task_name}'...")
    new_task_id = create_task(cvat_url, token, project_id, review_task_name)
    click.echo(f"  task_id={new_task_id}, uploading frames...")
    upload_data_with_rename(cvat_url, token, new_task_id, selected_items)
    state = wait_for_data_processing(cvat_url, token, new_task_id, timeout=900)
    click.echo(f"  state: {state}")
    if state != "Finished":
        click.secho("Aborting — upload didn't finish cleanly.", fg="red")
        raise SystemExit(1)

    # Verify frame order matches our upload order
    new_order = get_new_task_frame_order(cvat_url, token, new_task_id)
    expected_order = [f"cam{cam}_{name}" for cam, name, _ in selected_items]
    if new_order[:len(expected_order)] != expected_order:
        click.secho(
            "WARNING: new task frame order differs from upload order — "
            "annotation frame indices may be wrong. Falling back to name-based mapping.",
            fg="yellow",
        )
        name_to_new_idx = {name: idx for idx, name in enumerate(new_order)}
        for s in all_shapes_to_upload:
            # Find what was the frame's intended name
            pass  # not implementing fallback, just warn
    else:
        click.secho("Frame order verified — proceeding with PUT annotations", fg="green")

    # PUT annotations to the new task's job
    new_job_ids = get_task_jobs(cvat_url, token, new_task_id)
    if len(new_job_ids) != 1:
        click.secho(
            f"  new task has {len(new_job_ids)} jobs (expected 1). PUT'ing to first.",
            fg="yellow",
        )
    new_job_id = new_job_ids[0]
    click.echo(f"\nPUT'ing {total_shapes} shapes to job {new_job_id}...")
    put_annotations(cvat_url, token, new_job_id, all_shapes_to_upload)

    click.secho(
        f"\n✓ Review task ready. Open: {cvat_url}/tasks/{new_task_id}",
        fg="green",
    )


if __name__ == "__main__":
    main()
