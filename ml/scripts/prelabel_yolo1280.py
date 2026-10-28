"""Черновые рамки YOLOv8 1280 для выборки разметки: три копии (зерна 0–2),
находка остаётся, если её подтвердили две из трёх (то же голосование, что в
боевом детекторе), и только если её центр в зоне площадки.

    ml/venv/bin/python ml/scripts/prelabel_yolo1280.py --sel sel_v9 \
        --weights /mnt/c/Users/killh/Desktop/runs/detect/runs/yolo_loso_1280 --fold 0

Результат — data/round2/<sel>/prelabels_yolo1280.json:
{имя кадра: [[cx, cy, w, h, conf, class], ...]} в долях кадра, классы старой
модели (0 — бак, 1 — переполненный бак, 2 — мусор на земле).
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
import numpy as np
from PIL import Image

ML_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ML_ROOT.parent / "backend"))

from app.ml.detector import Detector  # noqa: E402
from app.ml.roi import RoiConfig, inside  # noqa: E402

ROI_CONFIG = ML_ROOT / "configs" / "cameras_roi_v2.json"


@click.command()
@click.option("--sel", default="sel_v9")
@click.option("--weights", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--fold", default=0)
@click.option("--skip-camera", multiple=True, default=["w11"])
def main(sel: str, weights: Path, fold: int, skip_camera: tuple[str, ...]) -> None:
    from ultralytics import YOLO

    sel_dir = ML_ROOT / "data" / "round2" / sel
    rows = [r for r in csv.DictReader(open(sel_dir / "manifest.csv", encoding="utf-8"))
            if r["camera"] not in skip_camera]
    models = [YOLO(str(weights / f"fold_{fold}_seed_{s}" / "weights" / "best.pt")) for s in range(3)]
    fuser = Detector(".", conf_threshold=0.25, min_votes=2)
    roi = RoiConfig.load(ROI_CONFIG)

    out_file = sel_dir / "prelabels_yolo1280.json"
    result = json.loads(out_file.read_text()) if out_file.exists() else {}
    todo = [r for r in rows if r["file"] not in result]
    click.echo(f"кадров {len(rows)}, уже готово {len(result)}, считаю {len(todo)}")
    for i, r in enumerate(todo, 1):
        img = Image.open(sel_dir / "frames" / r["file"]).convert("RGB")
        per_model = []
        for m in models:
            b = m.predict(img, imgsz=1280, conf=0.25, iou=0.3, verbose=False, device="cpu")[0].boxes
            rows_m = (np.concatenate([b.xywhn.numpy(), b.conf.numpy()[:, None], b.cls.numpy()[:, None]], axis=1)
                      if len(b) else np.empty((0, 6)))
            per_model.append(rows_m.astype(np.float32))
        fused = fuser._fuse(per_model)
        key = r["camera"]
        if roi.has(key):
            rects = roi.rects_at(key, datetime.now(timezone.utc))   # зоны камер Watcher от времени не зависят
            fused = [row for row in fused if inside(rects, row[0], row[1], *img.size)]
        result[r["file"]] = [[round(float(v), 5) for v in row] for row in fused]
        if i % 25 == 0 or i == len(todo):
            out_file.write_text(json.dumps(result))
            click.echo(f"  {i}/{len(todo)}")
    click.echo(f"готово: {out_file}")


if __name__ == "__main__":
    main()
