"""Загрузка итоговой выборки разметки №2 в CVAT (октябрь 2026).

Создаёт проект с метками разметки №2 и 16 заданий, по одному заданию (job)
в каждом, назначенных разметчикам:
- «Пачка N — razmetchikN» — кадры пачки N с черновыми рамками боевой модели
  (state из класса модели, type = «не указан»);
- «Общий набор — razmetchikN» — 33 общих кадра БЕЗ черновых рамок, у каждого
  своя копия (замер согласия команды).
Кадры в задании — по камерам, внутри камеры по времени (для клавиши R).

    CVAT_USER=arseniy CVAT_PASSWORD=... ml/venv/bin/python ml/scripts/cvat_upload_round2.py

Результат (id проекта, заданий, порядок кадров) — data/round2/<sel>/cvat_tasks.json.
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

ML_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ML_ROOT / "src"))

from datasets.cvat_round2 import order_frames, prelabel_to_shape  # noqa: E402

# Совпадает с LABELS в ml/cvat/razmetka/test/tools.e2e.test.mjs — горячие
# клавиши (tools.js) опираются на эти имена.
LABELS = [
    {
        "name": "bin",
        "attributes": [
            {"name": "state", "mutable": True, "input_type": "select",
             "default_value": "не указано", "values": ["не указано", "пусто", "есть мусор", "переполнение"]},
            {"name": "type", "mutable": True, "input_type": "select",
             "default_value": "не указан", "values": ["не указан", "евробак", "контейнер", "бутылки"]},
        ],
    },
    {"name": "ground_trash", "attributes": []},
]
FRAME_SIZE = (2560, 1440)
N_PEOPLE = 8


@click.command()
@click.option("--sel", default="sel_v4", help="каталог выборки в data/round2")
@click.option("--url", default="https://leti-metla.ru:8443")
@click.option("--project-name", default="Разметка №2 — октябрь 2026")
def main(sel: str, url: str, project_name: str) -> None:
    session = requests.Session()
    session.auth = (os.environ["CVAT_USER"], os.environ["CVAT_PASSWORD"])

    def api(method: str, path: str, **kwargs):
        resp = session.request(method, url + path, timeout=900, **kwargs)
        if not resp.ok:
            raise click.ClickException(f"{method} {path} → {resp.status_code}: {resp.text[:400]}")
        return resp.json() if resp.content else None

    existing = api("GET", "/api/projects", params={"search": project_name})["results"]
    if any(p["name"] == project_name for p in existing):
        raise click.ClickException(f"проект «{project_name}» уже есть — повторно не гружу")

    sel_dir = ML_ROOT / "data" / "round2" / sel
    rows = list(csv.DictReader(open(sel_dir / "manifest.csv", encoding="utf-8")))
    prelabels = json.loads((sel_dir / "prelabels.json").read_text())
    users = {u["username"]: u["id"] for u in api("GET", "/api/users", params={"page_size": 100})["results"]}

    common = order_frames([r["file"] for r in rows if r["pack"] == "общий"])
    plan = [
        (f"Пачка {p} — razmetchik{p}", f"razmetchik{p}",
         order_frames([r["file"] for r in rows if r["pack"] == str(p)]), True)
        for p in range(1, N_PEOPLE + 1)
    ] + [
        (f"Общий набор — razmetchik{p}", f"razmetchik{p}", common, False)
        for p in range(1, N_PEOPLE + 1)
    ]
    assert sum(len(f) for _, _, f, pre in plan if pre) + len(common) == len(rows)

    project = api("POST", "/api/projects", json={"name": project_name, "labels": LABELS})
    labels = api("GET", "/api/labels", params={"project_id": project["id"], "page_size": 100})["results"]
    label_ids = {lab["name"]: lab["id"] for lab in labels}
    attr_ids = {a["name"]: a["id"] for lab in labels if lab["name"] == "bin" for a in lab["attributes"]}
    click.echo(f"проект {project['id']}: «{project_name}»")

    done = []
    for name, username, files, with_prelabels in plan:
        task = api("POST", "/api/tasks", json={
            "name": name, "project_id": project["id"], "assignee_id": users[username],
        })
        handles = [open(sel_dir / "frames" / f, "rb") for f in files]
        try:
            rq = api("POST", f"/api/tasks/{task['id']}/data", data={
                "image_quality": 90, "sorting_method": "predefined",
            }, files=[(f"client_files[{i}]", (f, h, "image/jpeg")) for i, (f, h) in enumerate(zip(files, handles))])
        finally:
            for h in handles:
                h.close()
        for _ in range(600):
            status = api("GET", f"/api/requests/{rq['rq_id']}")["status"]
            if status == "finished":
                break
            if status == "failed":
                raise click.ClickException(f"{name}: загрузка кадров упала")
            time.sleep(1)

        meta = api("GET", f"/api/tasks/{task['id']}/data/meta")
        names = [Path(fr["name"]).name for fr in meta["frames"]]
        if names != files:
            raise click.ClickException(f"{name}: порядок кадров на сервере не совпал с заданным")

        jobs = api("GET", "/api/jobs", params={"task_id": task["id"]})["results"]
        if len(jobs) != 1:
            raise click.ClickException(f"{name}: ожидалось одно задание (job), получено {len(jobs)}")
        job_id = jobs[0]["id"]
        api("PATCH", f"/api/jobs/{job_id}", json={"assignee": users[username]})

        shapes = []
        if with_prelabels:
            shapes = [
                prelabel_to_shape(row, frame=i, size=FRAME_SIZE, label_ids=label_ids, attr_ids=attr_ids)
                for i, f in enumerate(files) for row in prelabels.get(f, [])
            ]
            api("PUT", f"/api/jobs/{job_id}/annotations",
                json={"version": 0, "tags": [], "shapes": shapes, "tracks": []})
            saved = api("GET", f"/api/jobs/{job_id}/annotations")["shapes"]
            if len(saved) != len(shapes):
                raise click.ClickException(f"{name}: легло {len(saved)} рамок из {len(shapes)}")

        done.append({"task": name, "task_id": task["id"], "job_id": job_id, "assignee": username,
                     "frames": files, "prelabels": len(shapes)})
        click.echo(f"  {name}: задание {task['id']}, кадров {len(files)}, черновых рамок {len(shapes)}")

    out = sel_dir / "cvat_tasks.json"
    out.write_text(json.dumps({"url": url, "project_id": project["id"], "project": project_name,
                               "tasks": done}, ensure_ascii=False, indent=2))
    click.echo(f"готово: {len(done)} заданий, сводка — {out}")


if __name__ == "__main__":
    main()
