"""Create CVAT review task with CLAHE-preprocessed night frames + existing labels.

For each source task (cam_1..cam_7):
  - Fetch existing annotations (already-labeled bboxes)
  - Filter to night frames by filename hour (default 20..05)
  - Apply CLAHE (clip=4, tile=8) on V channel of HSV to each source image
  - Encode CLAHE result back to JPEG bytes
Then create a new task `cam_night_clahe`, upload CLAHE images with `cam<X>_`
filename prefix, and PUT the (remapped) annotations.

Run on 4090 host (where CVAT runs locally) after labels exist in source tasks:
    python scripts/cvat_create_night_clahe_task.py \
        --cvat-url http://localhost:8080 \
        --project-id 1 \
        --to-label-dir data/processed/to_label
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import click
import cv2
import numpy as np
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


HOUR_RE = re.compile(r"\d{4}-\d{2}-\d{2}_(\d{2})\d{4}")


def is_night_frame(name: str, night_hours: set[int]) -> bool:
    m = HOUR_RE.search(Path(name).stem)
    if not m:
        return False
    return int(m.group(1)) in night_hours


def apply_clahe_v(jpeg_bytes: bytes, clip: float, tile: int, quality: int) -> bytes:
    """Decode JPEG, CLAHE on V channel of HSV, re-encode JPEG."""
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError("imdecode returned None")
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(tile, tile))
    hsv[:, :, 2] = clahe.apply(hsv[:, :, 2])
    out = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    ok, enc = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("imencode failed")
    return enc.tobytes()


def upload_clahe_data(
    cvat_url: str,
    token: str,
    task_id: int,
    items: list[tuple[str, str, bytes]],
) -> None:
    """items = [(camera_id, original_filename, clahe_jpeg_bytes)]."""
    files = []
    for i, (cam, orig_name, jpg) in enumerate(items):
        new_name = f"cam{cam}_{orig_name}"
        files.append((f"client_files[{i}]", (new_name, jpg, "image/jpeg")))
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
        timeout=1800,
    )
    r.raise_for_status()


def get_new_task_frame_order(cvat_url: str, token: str, task_id: int) -> list[str]:
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
    payload = {"version": 0, "tags": [], "shapes": shapes, "tracks": []}
    r = requests.put(
        f"{cvat_url}/api/jobs/{job_id}/annotations",
        headers={
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=300,
    )
    if not r.ok:
        click.secho(
            f"  PUT annotations failed: {r.status_code} {r.text[:500]}", fg="red"
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
@click.option("--task-prefix", default="cam_")
@click.option(
    "--skip-tasks",
    default="cam_IRR,cam_review,cam_night_clahe",
)
@click.option("--review-task-name", default="cam_night_clahe")
@click.option(
    "--night-hours",
    default="20,21,22,23,0,1,2,3,4,5",
    help="Comma-separated hours considered 'night' (filename-based)",
)
@click.option("--clahe-clip", type=float, default=4.0)
@click.option("--clahe-tile", type=int, default=8)
@click.option("--jpeg-quality", type=int, default=92)
def main(
    cvat_url: str,
    project_id: int,
    user: str,
    password: str,
    to_label_dir: Path,
    task_prefix: str,
    skip_tasks: str,
    review_task_name: str,
    night_hours: str,
    clahe_clip: float,
    clahe_tile: int,
    jpeg_quality: int,
) -> None:
    skip = {s.strip() for s in skip_tasks.split(",") if s.strip()}
    night_set = {int(h) for h in night_hours.split(",") if h.strip()}
    click.echo(f"Night hours: {sorted(night_set)}")
    click.echo(f"CLAHE clip={clahe_clip} tile={clahe_tile}, JPEG q={jpeg_quality}")

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

    selected_items: list[tuple[str, str, bytes]] = []
    all_shapes_to_upload: list[dict] = []
    frame_idx_counter = 0
    seen_filenames: set[str] = set()
    per_cam_counts: dict[str, int] = {}

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

        click.echo(f"\n[{cam}] fetching meta + annotations from task {task['id']}...")
        all_meta: list[dict] = []
        all_shapes_by_frame: dict[int, list] = {}
        for job_id in job_ids:
            meta = get_job_meta(cvat_url, token, job_id)
            ann = get_job_annotations(cvat_url, token, job_id)
            for s in ann.get("shapes", []):
                all_shapes_by_frame.setdefault(s["frame"], []).append(s)
            all_meta.extend(meta)

        cam_night = 0
        cam_missing = 0
        for src_idx, frame_meta in enumerate(all_meta):
            orig_name = Path(frame_meta["name"]).name
            if not is_night_frame(orig_name, night_set):
                continue
            source_path = cam_dir / orig_name
            if not source_path.exists():
                cam_missing += 1
                continue
            new_name = f"cam{cam}_{orig_name}"
            if new_name in seen_filenames:
                continue
            seen_filenames.add(new_name)

            jpg = apply_clahe_v(
                source_path.read_bytes(),
                clip=clahe_clip,
                tile=clahe_tile,
                quality=jpeg_quality,
            )
            selected_items.append((cam, orig_name, jpg))
            cam_night += 1

            for s in all_shapes_by_frame.get(src_idx, []):
                if s["type"] != "rectangle":
                    continue
                all_shapes_to_upload.append(
                    {
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
                )

            frame_idx_counter += 1

        per_cam_counts[cam] = cam_night
        click.secho(
            f"  [{cam}] {cam_night} night frames CLAHE'd, "
            f"missing src={cam_missing}, shapes so far={len(all_shapes_to_upload)}",
            fg="green",
        )

    total_items = len(selected_items)
    total_shapes = len(all_shapes_to_upload)
    click.echo(f"\nPer-cam night counts: {per_cam_counts}")
    click.echo(f"=== will upload {total_items} CLAHE frames with {total_shapes} bboxes ===")

    if total_items == 0:
        click.secho("Nothing to upload — aborting.", fg="red")
        raise SystemExit(1)

    click.echo(f"\nCreating task '{review_task_name}'...")
    new_task_id = create_task(cvat_url, token, project_id, review_task_name)
    click.echo(f"  task_id={new_task_id}, uploading frames...")
    upload_clahe_data(cvat_url, token, new_task_id, selected_items)
    state = wait_for_data_processing(cvat_url, token, new_task_id, timeout=1800)
    click.echo(f"  state: {state}")
    if state != "Finished":
        click.secho("Aborting — upload didn't finish cleanly.", fg="red")
        raise SystemExit(1)

    new_order = get_new_task_frame_order(cvat_url, token, new_task_id)
    expected_order = [f"cam{cam}_{name}" for cam, name, _ in selected_items]
    if new_order[: len(expected_order)] != expected_order:
        click.secho(
            "WARNING: new task frame order differs from upload order — "
            "remapping shape frame indices by filename.",
            fg="yellow",
        )
        name_to_new_idx = {name: idx for idx, name in enumerate(new_order)}
        old_idx_to_name = {
            old_idx: f"cam{cam}_{name}"
            for old_idx, (cam, name, _) in enumerate(selected_items)
        }
        for s in all_shapes_to_upload:
            old_idx = s["frame"]
            new_name = old_idx_to_name.get(old_idx)
            if new_name is None or new_name not in name_to_new_idx:
                click.secho(
                    f"  could not remap shape with frame={old_idx} → drop", fg="yellow"
                )
                s["frame"] = -1
                continue
            s["frame"] = name_to_new_idx[new_name]
        all_shapes_to_upload = [s for s in all_shapes_to_upload if s["frame"] >= 0]
    else:
        click.secho("Frame order verified — proceeding with PUT annotations", fg="green")

    new_job_ids = get_task_jobs(cvat_url, token, new_task_id)
    if len(new_job_ids) != 1:
        click.secho(
            f"  new task has {len(new_job_ids)} jobs (expected 1). PUT'ing to first.",
            fg="yellow",
        )
    new_job_id = new_job_ids[0]
    click.echo(f"\nPUT'ing {len(all_shapes_to_upload)} shapes to job {new_job_id}...")
    put_annotations(cvat_url, token, new_job_id, all_shapes_to_upload)

    click.secho(
        f"\n✓ Night-CLAHE review task ready. Open: {cvat_url}/tasks/{new_task_id}",
        fg="green",
    )


if __name__ == "__main__":
    main()
