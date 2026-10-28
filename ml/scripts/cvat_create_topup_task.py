"""Create CVAT tasks per working camera and upload sampled frames.

Reads `ml/data/processed/to_label/<cam_id>/*.jpg` (sample_dataset.py output) and
creates one CVAT task per camera under the existing project, uploading frames.

Run on 4090 host (where CVAT runs locally) after sample_dataset.py completes:

    python scripts/cvat_create_tasks.py \
        --cvat-url http://localhost:8080 \
        --project-id 1 \
        --user alex --pass nekobak2026 \
        --to-label-dir data/processed/to_label
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import click
import requests


def login(cvat_url: str, user: str, password: str) -> str:
    r = requests.post(
        f"{cvat_url}/api/auth/login",
        json={"username": user, "password": password},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["key"]


def list_existing_tasks(cvat_url: str, token: str, project_id: int) -> dict[str, int]:
    """Return {task_name: task_id} for tasks belonging to project_id."""
    out: dict[str, int] = {}
    page = 1
    while True:
        r = requests.get(
            f"{cvat_url}/api/tasks",
            params={"project_id": project_id, "page": page, "page_size": 100},
            headers={"Authorization": f"Token {token}"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        for task in data.get("results", []):
            out[task["name"]] = task["id"]
        if not data.get("next"):
            break
        page += 1
    return out


def create_task(
    cvat_url: str, token: str, project_id: int, name: str, subset: str = "train"
) -> int:
    r = requests.post(
        f"{cvat_url}/api/tasks",
        json={"name": name, "project_id": project_id, "subset": subset},
        headers={"Authorization": f"Token {token}"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["id"]


def upload_data(
    cvat_url: str, token: str, task_id: int, image_paths: list[Path], image_quality: int = 95
) -> None:
    """Upload images to a task using CVAT's single-request multipart protocol.

    CVAT 2.x accepts a single POST with all client_files + parameters; no need for
    the TUS-like Upload-Start/Multiple/Finish dance.
    """
    files = []
    for i, p in enumerate(image_paths):
        files.append((f"client_files[{i}]", (p.name, p.read_bytes(), "image/jpeg")))

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


def wait_for_data_processing(cvat_url: str, token: str, task_id: int, timeout: int = 600) -> str:
    """Poll task status until image processing is done. Returns final state."""
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(
            f"{cvat_url}/api/tasks/{task_id}/status",
            headers={"Authorization": f"Token {token}"},
            timeout=15,
        )
        r.raise_for_status()
        state = r.json()
        if state.get("state") in ("Finished", "Failed"):
            return state.get("state")
        time.sleep(3)
    return "Timeout"


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
@click.option(
    "--cameras",
    default="1,2,3,5,7",
    help="Comma-separated working camera ids; one task per camera created",
)
@click.option("--image-quality", type=int, default=95)
def main(
    cvat_url: str,
    project_id: int,
    user: str,
    password: str,
    to_label_dir: Path,
    cameras: str,
    image_quality: int,
) -> None:
    cams = [c.strip() for c in cameras.split(",") if c.strip()]
    token = login(cvat_url, user, password)
    click.echo(f"Logged in as {user}, token={token[:10]}…")

    existing = list_existing_tasks(cvat_url, token, project_id)
    click.echo(f"Existing tasks in project {project_id}: {list(existing.keys()) or 'none'}")

    for cam in cams:
        cam_dir = to_label_dir / cam
        if not cam_dir.exists():
            click.secho(f"  [{cam}] directory missing — sample_dataset finished?", fg="yellow")
            continue

        images = sorted(cam_dir.glob("*.jpg"))
        if not images:
            click.secho(f"  [{cam}] no images, skipping", fg="yellow")
            continue

        task_name = f"cam_{cam}_topup_may"
        if task_name in existing:
            click.secho(
                f"  [{cam}] task '{task_name}' already exists (id={existing[task_name]}), skipping create",
                fg="yellow",
            )
            continue

        click.echo(f"  [{cam}] creating task '{task_name}' with {len(images)} images")
        task_id = create_task(cvat_url, token, project_id, task_name)
        click.echo(f"    task_id={task_id}, uploading…")
        try:
            upload_data(cvat_url, token, task_id, images, image_quality=image_quality)
        except requests.HTTPError as e:
            click.secho(f"    upload failed: {e} — response: {e.response.text[:300]}", fg="red")
            continue
        state = wait_for_data_processing(cvat_url, token, task_id, timeout=900)
        click.secho(
            f"    state: {state} — open: {cvat_url}/tasks/{task_id}",
            fg="green" if state == "Finished" else "yellow",
        )

    click.echo("\nAll done. Open project: " + f"{cvat_url}/projects/{project_id}")


if __name__ == "__main__":
    main()
