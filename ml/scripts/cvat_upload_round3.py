"""Загрузка кадров в CVAT по схеме разметки от 13.10.2026.

Кадры: старый набор (1498 кадров, data/processed/to_label, черновые рамки —
человеческая разметка первого захода) и выборка с камер Watcher (data/round2/<sel>,
без w11, черновые рамки — YOLOv8 1280, prelabels_yolo1280.json). Двойные рамки
убираются. Раскладка — пачки по 100 кадров (по камерам, внутри — по времени),
без назначения; плюс «Общий набор — razmetchikN» без черновых рамок для замера
согласия.

Повторный запуск безопасен: готовые пачки пропускаются, недогруженные пересоздаются.

    CVAT_USER=arseniy CVAT_PASSWORD=... ml/venv/bin/python ml/scripts/cvat_upload_round3.py

Сводка — data/round3/cvat_tasks.json.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path

import click
import requests
from PIL import Image

ML_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ML_ROOT / "src"))

from datasets.cvat_round2 import order_frames  # noqa: E402
from datasets.cvat_round3 import LABELS, buckets, dedupe, row_to_shape, upload_name, yolo_txt_rows  # noqa: E402

OLD = ML_ROOT / "data" / "processed"
OUT = ML_ROOT / "data" / "round3"
N_PEOPLE = 8


def collect(sel: str, skip: set[str]) -> tuple[list[dict], list[str]]:
    """Все кадры: {name, path, rows | None}; и общий набор (имена в CVAT)."""
    items = []
    for cam_dir in sorted(p for p in (OLD / "to_label").iterdir() if p.is_dir()):
        for img in sorted(cam_dir.glob("*.jpg")):
            txt = OLD / "labeled" / cam_dir.name / f"{img.stem}.txt"
            items.append({"name": upload_name(cam_dir.name, img.name), "path": img,
                          "rows": yolo_txt_rows(txt.read_text()) if txt.exists() else []})
    sel_dir = ML_ROOT / "data" / "round2" / sel
    pre_file = sel_dir / "prelabels_yolo1280.json"
    pre = json.loads(pre_file.read_text()) if pre_file.exists() else {}
    common = []
    for r in csv.DictReader(open(sel_dir / "manifest.csv", encoding="utf-8")):
        if r["camera"] in skip:
            continue
        items.append({"name": r["file"], "path": sel_dir / "frames" / r["file"], "rows": pre.get(r["file"])})
        if r["pack"] == "общий":
            common.append(r["file"])
    by_name = {it["name"]: it for it in items}
    assert len(by_name) == len(items), "имена кадров повторяются"
    ordered = [by_name[n] for n in order_frames(list(by_name))]
    return ordered, order_frames(common)


@click.command()
@click.option("--sel", default="sel_v9")
@click.option("--skip-camera", multiple=True, default=["w11"])
@click.option("--url", default="https://leti-metla.ru:8443")
@click.option("--project-name", default="Разметка — новая схема (октябрь 2026)")
def main(sel: str, skip_camera: tuple[str, ...], url: str, project_name: str) -> None:
    session = requests.Session()
    session.auth = (os.environ["CVAT_USER"], os.environ["CVAT_PASSWORD"])

    def api(method: str, path: str, **kwargs):
        for attempt in range(3):
            try:
                resp = session.request(method, url + path, timeout=900, **kwargs)
                break
            except requests.ConnectionError:
                if attempt == 2 or "files" in kwargs:
                    raise
                time.sleep(5)
        if not resp.ok:
            raise click.ClickException(f"{method} {path} → {resp.status_code}: {resp.text[:400]}")
        return resp.json() if resp.content else None

    items, common = collect(sel, set(skip_camera))
    by_name = {it["name"]: it for it in items}
    items_names = [it["name"] for it in items]
    plan = [(f"Пачка {i:02d}", None, chunk, True) for i, chunk in enumerate(buckets(items_names, 100), 1)]
    plan += [(f"Общий набор — razmetchik{p}", f"razmetchik{p}", common, False) for p in range(1, N_PEOPLE + 1)]
    click.echo(f"кадров {len(items_names)}: пачек {sum(1 for p in plan if p[3])}, общий набор {len(common)} × {N_PEOPLE}")

    found = [p for p in api("GET", "/api/projects", params={"search": project_name})["results"]
             if p["name"] == project_name]
    project = found[0] if found else api("POST", "/api/projects", json={"name": project_name, "labels": LABELS})
    labels = api("GET", "/api/labels", params={"project_id": project["id"], "page_size": 100})["results"]
    label_ids = {lab["name"]: lab["id"] for lab in labels}
    attr_ids = {a["name"]: a["id"] for lab in labels if lab["name"] == "bin" for a in lab["attributes"]}
    users = {u["username"]: u["id"] for u in api("GET", "/api/users", params={"page_size": 100})["results"]}
    existing = {t["name"]: t for t in api("GET", "/api/tasks", params={"project_id": project["id"], "page_size": 100})["results"]}
    click.echo(f"проект {project['id']}: «{project_name}»{' (уже был)' if found else ''}")

    OUT.mkdir(parents=True, exist_ok=True)
    summary_file = OUT / "cvat_tasks.json"
    summary = json.loads(summary_file.read_text()) if summary_file.exists() else {"tasks": {}}
    summary.update(url=url, project_id=project["id"], project=project_name)

    for name, username, files, with_prelabels in plan:
        if with_prelabels and any(by_name[f]["rows"] is None for f in files):
            click.secho(f"  {name}: черновые рамки YOLO ещё не готовы — пропускаю", fg="yellow")
            continue
        old = existing.get(name)
        if old and old.get("size") == len(files) and name in summary["tasks"]:
            click.echo(f"  {name}: уже загружена (задание {old['id']})")
            continue
        if old:
            api("DELETE", f"/api/tasks/{old['id']}")   # недогруженная — заново

        task = api("POST", "/api/tasks", json={"name": name, "project_id": project["id"],
                                               **({"assignee_id": users[username]} if username else {})})
        handles = [open(by_name[f]["path"], "rb") for f in files]
        try:
            rq = api("POST", f"/api/tasks/{task['id']}/data", data={
                "image_quality": 90, "sorting_method": "predefined",
            }, files=[(f"client_files[{i}]", (f, h, "image/jpeg")) for i, (f, h) in enumerate(zip(files, handles))])
        finally:
            for h in handles:
                h.close()
        for _ in range(1200):
            status = api("GET", f"/api/requests/{rq['rq_id']}")["status"]
            if status == "finished":
                break
            if status == "failed":
                raise click.ClickException(f"{name}: загрузка кадров упала")
            time.sleep(1)

        meta = api("GET", f"/api/tasks/{task['id']}/data/meta")
        if [Path(fr["name"]).name for fr in meta["frames"]] != files:
            raise click.ClickException(f"{name}: порядок кадров на сервере не совпал с заданным")
        jobs = api("GET", "/api/jobs", params={"task_id": task["id"]})["results"]
        if len(jobs) != 1:
            raise click.ClickException(f"{name}: ожидалось одно задание (job), получено {len(jobs)}")
        job_id = jobs[0]["id"]
        if username:
            api("PATCH", f"/api/jobs/{job_id}", json={"assignee": users[username]})

        shapes = []
        if with_prelabels:
            for i, f in enumerate(files):
                size = Image.open(by_name[f]["path"]).size
                shapes += [row_to_shape(r, i, size, label_ids, attr_ids) for r in dedupe(by_name[f]["rows"])]
            api("PUT", f"/api/jobs/{job_id}/annotations", json={"version": 0, "tags": [], "shapes": shapes, "tracks": []})
            saved = api("GET", f"/api/jobs/{job_id}/annotations")["shapes"]
            if len(saved) != len(shapes):
                raise click.ClickException(f"{name}: легло {len(saved)} рамок из {len(shapes)}")

        summary["tasks"][name] = {"task_id": task["id"], "job_id": job_id, "assignee": username,
                                  "frames": files, "prelabels": len(shapes)}
        summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=1))
        click.echo(f"  {name}: задание {task['id']}, кадров {len(files)}, черновых рамок {len(shapes)}")

    click.echo(f"готово: сводка — {summary_file}")


if __name__ == "__main__":
    main()
