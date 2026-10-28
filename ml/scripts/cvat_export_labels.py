"""Export YOLO-format labels from CVAT tasks 11-15 (one per camera).

For each task:
  - GET annotations via REST API (JSON)
  - GET frame metadata (filenames + dimensions)
  - Convert each shape's pixel bbox to YOLO format (class_id cx cy w h, normalized)
  - Write `<frame_stem>.txt` per frame to data/processed/labeled/<cam>/

Run on 4090 host:
    python scripts/cvat_export_labels.py \\
        --cvat-url http://localhost:8080 \\
        --project-id 1 \\
        --out-dir data/processed/labeled

Empty frames produce an empty .txt file (zero bboxes). Class IDs are derived
from the project's label set (label name → 0-indexed position).
"""

from __future__ import annotations

import json
from pathlib import Path

import click
import requests

from cvat_create_tasks import login


CLASS_ORDER = ["bin_ok", "bin_overflow", "ground_trash"]


def get_project_labels(cvat_url: str, token: str, project_id: int) -> dict[int, str]:
    r = requests.get(
        f"{cvat_url}/api/labels?project_id={project_id}&page_size=100",
        headers={"Authorization": f"Token {token}"},
        timeout=15,
    )
    r.raise_for_status()
    out = {}
    for label in r.json().get("results", []):
        out[label["id"]] = label["name"]
    return out


def list_tasks_in_project(cvat_url: str, token: str, project_id: int) -> list[dict]:
    out = []
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
        out.extend(data.get("results", []))
        if not data.get("next"):
            break
        page += 1
    return out


def get_task_jobs(cvat_url: str, token: str, task_id: int) -> list[int]:
    r = requests.get(
        f"{cvat_url}/api/jobs?task_id={task_id}&page_size=100",
        headers={"Authorization": f"Token {token}"},
        timeout=15,
    )
    r.raise_for_status()
    return [j["id"] for j in r.json().get("results", [])]


def get_job_meta(cvat_url: str, token: str, job_id: int) -> list[dict]:
    """Returns list of {name, width, height} per frame index."""
    r = requests.get(
        f"{cvat_url}/api/jobs/{job_id}/data/meta",
        headers={"Authorization": f"Token {token}"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    return data.get("frames", [])


def get_job_annotations(cvat_url: str, token: str, job_id: int) -> dict:
    r = requests.get(
        f"{cvat_url}/api/jobs/{job_id}/annotations",
        headers={"Authorization": f"Token {token}"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def points_to_yolo(points: list[float], img_w: int, img_h: int) -> tuple[float, float, float, float]:
    """CVAT rectangle: [x1, y1, x2, y2] (pixels) → YOLO (cx, cy, w, h) normalized."""
    x1, y1, x2, y2 = points
    cx = (x1 + x2) / 2 / img_w
    cy = (y1 + y2) / 2 / img_h
    w = abs(x2 - x1) / img_w
    h = abs(y2 - y1) / img_h
    return cx, cy, w, h


@click.command()
@click.option("--cvat-url", default="http://localhost:8080")
@click.option("--project-id", type=int, required=True)
@click.option("--user", default="alex")
@click.option("--pass", "password", default="nekobak2026")
@click.option(
    "--out-dir",
    type=click.Path(path_type=Path),
    default=Path("data/processed/labeled"),
)
@click.option(
    "--task-prefix",
    default="cam_",
    help="Only export tasks whose name starts with this prefix (default 'cam_').",
)
@click.option(
    "--skip-tasks",
    default="cam_IRR,cam_review",
    help="Comma-separated task names to skip.",
)
def main(
    cvat_url: str,
    project_id: int,
    user: str,
    password: str,
    out_dir: Path,
    task_prefix: str,
    skip_tasks: str,
) -> None:
    skip = {s.strip() for s in skip_tasks.split(",") if s.strip()}
    token = login(cvat_url, user, password)
    click.echo(f"Logged in as {user}")

    labels_map = get_project_labels(cvat_url, token, project_id)
    click.echo(f"Project labels: {labels_map}")

    name_to_cls_id = {}
    for cvat_label_id, name in labels_map.items():
        if name not in CLASS_ORDER:
            click.secho(
                f"  warning: label '{name}' not in expected CLASS_ORDER {CLASS_ORDER}; skipping",
                fg="yellow",
            )
            continue
        name_to_cls_id[cvat_label_id] = CLASS_ORDER.index(name)
    click.echo(f"CVAT label_id → class_id: {name_to_cls_id}")

    out_dir.mkdir(parents=True, exist_ok=True)

    tasks = list_tasks_in_project(cvat_url, token, project_id)
    click.echo(f"\nFound {len(tasks)} tasks in project {project_id}")

    summary: dict[str, dict[str, int]] = {}

    for task in tasks:
        task_name = task["name"]
        task_id = task["id"]
        if not task_name.startswith(task_prefix):
            continue
        if task_name in skip:
            click.echo(f"  [{task_name}] skipped (in --skip-tasks)")
            continue

        cam = task_name[len(task_prefix):]
        cam_dir = out_dir / cam
        cam_dir.mkdir(parents=True, exist_ok=True)

        click.echo(f"\n[{task_name}] task_id={task_id}, cam={cam}")
        job_ids = get_task_jobs(cvat_url, token, task_id)
        if not job_ids:
            click.secho(f"  no jobs in task — skip", fg="yellow")
            continue

        total_frames = 0
        empty_frames = 0
        cls_counts = {0: 0, 1: 0, 2: 0}

        for job_id in job_ids:
            meta = get_job_meta(cvat_url, token, job_id)
            ann = get_job_annotations(cvat_url, token, job_id)
            shapes = ann.get("shapes", [])

            shapes_by_frame: dict[int, list] = {}
            for s in shapes:
                shapes_by_frame.setdefault(s["frame"], []).append(s)

            for frame_idx, frame_meta in enumerate(meta):
                frame_name = frame_meta["name"]
                img_w = frame_meta["width"]
                img_h = frame_meta["height"]
                stem = Path(frame_name).stem

                out_path = cam_dir / f"{stem}.txt"
                lines: list[str] = []
                for s in shapes_by_frame.get(frame_idx, []):
                    if s["type"] != "rectangle":
                        continue
                    label_id = s["label_id"]
                    if label_id not in name_to_cls_id:
                        continue
                    cls_id = name_to_cls_id[label_id]
                    cx, cy, w, h = points_to_yolo(s["points"], img_w, img_h)
                    lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
                    cls_counts[cls_id] += 1

                out_path.write_text("\n".join(lines) + ("\n" if lines else ""))
                total_frames += 1
                if not lines:
                    empty_frames += 1

        summary[cam] = {
            "total_frames": total_frames,
            "empty_frames": empty_frames,
            "non_empty": total_frames - empty_frames,
            "bin_ok": cls_counts[0],
            "bin_overflow": cls_counts[1],
            "ground_trash": cls_counts[2],
        }
        click.secho(
            f"  [{cam}] {total_frames} frames, {empty_frames} empty, "
            f"bin_ok={cls_counts[0]}, bin_overflow={cls_counts[1]}, ground_trash={cls_counts[2]}",
            fg="green",
        )

    # Summary table
    click.echo("\n" + "=" * 80)
    click.echo("SUMMARY")
    click.echo("=" * 80)
    click.echo(f"{'cam':<6} {'frames':>8} {'empty':>7} {'non-empty':>10} {'bin_ok':>8} {'bin_overflow':>14} {'ground_trash':>14}")
    totals = {"total_frames": 0, "empty_frames": 0, "non_empty": 0, "bin_ok": 0, "bin_overflow": 0, "ground_trash": 0}
    for cam in sorted(summary.keys()):
        s = summary[cam]
        click.echo(
            f"{cam:<6} {s['total_frames']:>8} {s['empty_frames']:>7} {s['non_empty']:>10} "
            f"{s['bin_ok']:>8} {s['bin_overflow']:>14} {s['ground_trash']:>14}"
        )
        for k in totals:
            totals[k] += s[k]
    click.echo("-" * 80)
    click.echo(
        f"{'TOTAL':<6} {totals['total_frames']:>8} {totals['empty_frames']:>7} {totals['non_empty']:>10} "
        f"{totals['bin_ok']:>8} {totals['bin_overflow']:>14} {totals['ground_trash']:>14}"
    )

    # Persist summary JSON
    summary_path = out_dir / "_export_summary.json"
    summary_path.write_text(json.dumps({"per_cam": summary, "totals": totals}, indent=2, ensure_ascii=False))
    click.echo(f"\nSummary saved: {summary_path}")
    click.echo(f"Labels saved: {out_dir}/<cam>/<frame_stem>.txt")


if __name__ == "__main__":
    main()
