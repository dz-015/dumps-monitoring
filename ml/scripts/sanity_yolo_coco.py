"""Sanity test #1: run COCO-pretrained YOLOv8m on raw camera frames.

Goal: before any labeling or fine-tuning, verify that the pretrained detector
sees *something* in our frames where bins should be. If nothing fires near the
bin region on a camera, that camera is not usable for our task — we drop it
before spending labeling time on it.

Output: per-camera summary of detection counts + annotated images saved to
`out_dir/<camera_id>/<filename>` for visual inspection.

Run after `pip install -r ml/requirements-ml.txt` finishes; invoke from repo root:

    ./ml/venv/bin/python ml/scripts/sanity_yolo_coco.py \\
        --raw-dir ml/data/raw/audit_2026-04-29 \\
        --out-dir ml/data/raw/sanity_yolo_coco \\
        --conf 0.20
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import click


@click.command()
@click.option(
    "--raw-dir",
    type=click.Path(path_type=Path, exists=True, file_okay=False),
    required=True,
    help="Directory layout: <raw_dir>/<camera_id>/*.jpg",
)
@click.option(
    "--out-dir",
    type=click.Path(path_type=Path, file_okay=False),
    required=True,
    help="Where to write annotated images and per-camera summaries.",
)
@click.option(
    "--model",
    type=str,
    default="yolov8m.pt",
    help="Ultralytics weights name (downloaded automatically on first run).",
)
@click.option(
    "--conf",
    type=float,
    default=0.20,
    help="Confidence threshold. Low because we expect domain shift to drop scores.",
)
@click.option(
    "--imgsz",
    type=int,
    default=1280,
    help="Inference image size. 1280 helps with small/distant bins.",
)
def main(raw_dir: Path, out_dir: Path, model: str, conf: float, imgsz: int) -> None:
    from ultralytics import YOLO

    out_dir.mkdir(parents=True, exist_ok=True)
    yolo = YOLO(model)

    summary: dict[str, dict] = {}

    for cam_dir in sorted(p for p in raw_dir.iterdir() if p.is_dir()):
        cam_id = cam_dir.name
        cam_out = out_dir / cam_id
        cam_out.mkdir(parents=True, exist_ok=True)

        images = sorted(cam_dir.glob("*.jpg")) + sorted(cam_dir.glob("*.png"))
        if not images:
            click.echo(f"[{cam_id}] no images found, skipping")
            continue

        class_counts: Counter[str] = Counter()
        per_image_detections = 0
        zero_detection_frames = 0

        for img_path in images:
            results = yolo.predict(
                source=str(img_path),
                conf=conf,
                imgsz=imgsz,
                verbose=False,
                save=True,
                project=str(out_dir),
                name=cam_id,
                exist_ok=True,
            )
            r = results[0]
            n_dets = len(r.boxes) if r.boxes is not None else 0
            per_image_detections += n_dets
            if n_dets == 0:
                zero_detection_frames += 1
            for cls_idx in (r.boxes.cls.int().tolist() if r.boxes is not None else []):
                class_counts[r.names[cls_idx]] += 1

        summary[cam_id] = {
            "n_images": len(images),
            "total_detections": per_image_detections,
            "avg_detections_per_image": round(per_image_detections / len(images), 2),
            "zero_detection_frames": zero_detection_frames,
            "zero_detection_rate": round(zero_detection_frames / len(images), 3),
            "top_classes": class_counts.most_common(10),
        }

        click.echo(
            f"[{cam_id}] {len(images)} imgs | "
            f"avg dets/img: {summary[cam_id]['avg_detections_per_image']} | "
            f"zero-det rate: {summary[cam_id]['zero_detection_rate']} | "
            f"top: {summary[cam_id]['top_classes'][:3]}"
        )

    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    click.echo(f"\nsummary written to {summary_path}")
    click.echo(
        "\nDecision rule: if a camera has zero_detection_rate > 0.5 OR "
        "no relevant classes (bottle / suitcase / chair / bench / car for context) "
        "near the expected bin location, mark it as STRUCTURALLY UNFIT and drop "
        "from train/test before labeling."
    )


if __name__ == "__main__":
    main()
