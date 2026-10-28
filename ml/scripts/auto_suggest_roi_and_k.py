"""Heuristic K + ROI suggestion from COCO YOLOv8m predictions on audit frames.

Logic:
  1. Run yolov8m.pt on all audit frames per camera.
  2. Filter detections to bin-proxy classes (objects that COCO confuses with bins:
     bottle, cup, bowl, vase, suitcase, refrigerator, bench, chair).
  3. Compute per-camera:
     - Bin-proxy bbox union (with 30% margin) → candidate ROI
     - Count of bin-proxy detections, mean per frame
     - Heuristic K classification: рабочая / слабая / непригодная
  4. Output cameras_roi.json (auto-suggested) + report.md (Arseniy verifies).

The output is a STARTING POINT, not authoritative — manual ROI in viewer may differ.
But it's typically good enough to skip cold-start review.

Run on 4090 (or any machine with GPU) after audit:
    python scripts/auto_suggest_roi_and_k.py --raw-dir data/raw/audit_2026-05-04
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import click

BIN_PROXY_CLASSES = {"bottle", "cup", "bowl", "vase", "suitcase", "refrigerator", "bench", "chair"}
MARGIN = 0.30


def classify_camera(detections_per_frame: list[int], n_frames: int, bin_proxy_count: int) -> tuple[str, str]:
    """Return (status, reason) based on detection statistics.

    Heuristic — Arseniy will verify visually.
    """
    if n_frames == 0:
        return ("непригодная", "no audit frames")
    zero_rate = sum(1 for c in detections_per_frame if c == 0) / n_frames
    bin_proxy_per_frame = bin_proxy_count / n_frames

    if zero_rate > 0.5:
        return ("непригодная", f"zero-detection rate {zero_rate:.0%}")
    if bin_proxy_count == 0:
        return ("слабая", "no bin-proxy detections (COCO sees no bottle/suitcase/refrigerator/etc)")
    if bin_proxy_per_frame >= 0.3:
        return ("рабочая", f"{bin_proxy_count} bin-proxy detections in {n_frames} frames ({bin_proxy_per_frame:.2f}/frame)")
    return ("слабая", f"few bin-proxy detections: {bin_proxy_count} in {n_frames} frames ({bin_proxy_per_frame:.2f}/frame)")


def compute_union_with_margin(
    boxes_xyxy: list[tuple[float, float, float, float]],
    img_w: int,
    img_h: int,
    margin: float,
) -> tuple[int, int, int, int] | None:
    """Compute tight union of bboxes, then expand by margin on each side, clipped to image bounds."""
    if not boxes_xyxy:
        return None
    x1 = min(b[0] for b in boxes_xyxy)
    y1 = min(b[1] for b in boxes_xyxy)
    x2 = max(b[2] for b in boxes_xyxy)
    y2 = max(b[3] for b in boxes_xyxy)
    w = x2 - x1
    h = y2 - y1
    mx = w * margin
    my = h * margin
    return (
        max(0, int(x1 - mx)),
        max(0, int(y1 - my)),
        min(img_w, int(x2 + mx)),
        min(img_h, int(y2 + my)),
    )


@click.command()
@click.option(
    "--raw-dir",
    type=click.Path(path_type=Path, exists=True),
    default=Path("data/raw/audit_2026-05-04"),
)
@click.option(
    "--out-roi",
    type=click.Path(path_type=Path),
    default=Path("configs/cameras_roi.auto.json"),
)
@click.option(
    "--out-report",
    type=click.Path(path_type=Path),
    default=Path("data/raw/audit_2026-05-04/auto_classification_report.md"),
)
@click.option("--model", type=str, default="yolov8m.pt")
@click.option("--conf", type=float, default=0.20)
@click.option("--imgsz", type=int, default=1280)
def main(raw_dir: Path, out_roi: Path, out_report: Path, model: str, conf: float, imgsz: int) -> None:
    from PIL import Image
    from ultralytics import YOLO

    yolo = YOLO(model)

    rois: dict[str, list[int]] = {}
    classifications: dict[str, dict] = {}

    for cam_dir in sorted(p for p in raw_dir.iterdir() if p.is_dir()):
        cam_id = cam_dir.name
        images = sorted(cam_dir.glob("*.jpg"))
        if not images:
            continue

        with Image.open(images[0]) as im:
            img_w, img_h = im.size

        bin_boxes: list[tuple[float, float, float, float]] = []
        det_per_frame: list[int] = []
        bin_proxy_count = 0
        all_classes_count = defaultdict(int)

        for img_path in images:
            result = yolo.predict(source=str(img_path), conf=conf, imgsz=imgsz, verbose=False)[0]
            n_dets = len(result.boxes) if result.boxes is not None else 0
            det_per_frame.append(n_dets)
            if result.boxes is None:
                continue
            for cls_idx, xyxy in zip(result.boxes.cls.int().tolist(), result.boxes.xyxy.tolist()):
                cls_name = result.names[cls_idx]
                all_classes_count[cls_name] += 1
                if cls_name in BIN_PROXY_CLASSES:
                    bin_proxy_count += 1
                    bin_boxes.append(tuple(xyxy))

        # ROI from bin-proxies; if none, fall back to union of all detections (probably noise but better than nothing)
        roi_source = "bin-proxy classes"
        roi = compute_union_with_margin(bin_boxes, img_w, img_h, MARGIN)
        if roi is None and bin_proxy_count == 0:
            # Fallback: use centre 60% as ROI
            cx, cy = img_w // 2, img_h // 2
            roi = (
                max(0, cx - int(img_w * 0.4)),
                max(0, cy - int(img_h * 0.4)),
                min(img_w, cx + int(img_w * 0.4)),
                min(img_h, cy + int(img_h * 0.4)),
            )
            roi_source = "fallback: centre 60% (no bin-proxies detected)"

        status, reason = classify_camera(det_per_frame, len(images), bin_proxy_count)

        rois[cam_id] = list(roi) if roi else None
        classifications[cam_id] = {
            "status": status,
            "reason": reason,
            "n_audit_frames": len(images),
            "img_size": [img_w, img_h],
            "bin_proxy_detections": bin_proxy_count,
            "total_detections": sum(det_per_frame),
            "zero_detection_frames": sum(1 for c in det_per_frame if c == 0),
            "top_5_classes": sorted(all_classes_count.items(), key=lambda kv: -kv[1])[:5],
            "roi_xyxy": list(roi) if roi else None,
            "roi_source": roi_source,
        }

    out_roi.parent.mkdir(parents=True, exist_ok=True)
    out_roi.write_text(
        json.dumps(
            {
                "_README": "AUTO-SUGGESTED ROI from COCO YOLOv8m detections. Verify visually before using in sample_dataset.py.",
                "_HOW_TO_VERIFY": "Open one audit frame per camera in image viewer. Check ROI [x1,y1,x2,y2] visually contains all bins + ~30% margin. Edit if needed.",
                "_BIN_PROXY_CLASSES": list(BIN_PROXY_CLASSES),
                **{cam: roi for cam, roi in rois.items() if roi},
            },
            indent=2,
            ensure_ascii=False,
        )
    )

    # Markdown report
    lines = ["# Auto-classification report — audit 2026-05-04\n"]
    lines.append(f"Generated by `auto_suggest_roi_and_k.py` from COCO YOLOv8m predictions.\n")
    lines.append(f"Bin-proxy classes considered: {', '.join(sorted(BIN_PROXY_CLASSES))}.\n")
    lines.append(f"ROI margin: {MARGIN:.0%}.\n\n")
    lines.append("## Per-camera classification (Arseniy: verify visually)\n\n")
    lines.append("| Camera | Status | Reason | Bin-proxy det. | Total det. | Zero-det frames | Top classes |\n")
    lines.append("|---|---|---|---:|---:|---:|---|\n")
    for cam in sorted(classifications):
        c = classifications[cam]
        top_str = ", ".join(f"{name}={n}" for name, n in c["top_5_classes"])
        lines.append(
            f"| {cam} | **{c['status']}** | {c['reason']} | {c['bin_proxy_detections']} | "
            f"{c['total_detections']} | {c['zero_detection_frames']}/{c['n_audit_frames']} | {top_str} |\n"
        )

    lines.append("\n## ROI suggestions\n\n")
    lines.append("| Camera | Image size | ROI [x1,y1,x2,y2] | ROI size | Source |\n")
    lines.append("|---|---|---|---|---|\n")
    for cam in sorted(classifications):
        c = classifications[cam]
        if c["roi_xyxy"]:
            x1, y1, x2, y2 = c["roi_xyxy"]
            lines.append(
                f"| {cam} | {c['img_size'][0]}×{c['img_size'][1]} | "
                f"[{x1}, {y1}, {x2}, {y2}] | {x2 - x1}×{y2 - y1} | {c['roi_source']} |\n"
            )

    lines.append("\n## How Arseniy verifies\n\n")
    lines.append("1. Open `runs/detect/ml/data/raw/sanity_yolo_coco/<cam>/` (annotated frames with bbox overlay)\n")
    lines.append("2. For each camera marked **рабочая** — confirm bins are visible, ROI covers them with margin\n")
    lines.append("3. For each camera marked **слабая** — decide: include with caveats, or drop\n")
    lines.append("4. For each camera marked **непригодная** — confirm there are really no usable bins\n")
    lines.append(
        "5. Edit `ml/configs/cameras_roi.auto.json` → save as `cameras_roi.json` (drop .auto suffix)\n"
    )
    lines.append("6. Tell Claude the final list of working camera IDs to record in level1.yaml\n")

    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text("".join(lines))

    click.echo(f"ROI written to {out_roi}")
    click.echo(f"Report written to {out_report}")
    click.echo("\n=== Per-camera summary ===")
    for cam in sorted(classifications):
        c = classifications[cam]
        click.echo(f"  {cam}: {c['status']} ({c['reason']})")


if __name__ == "__main__":
    main()
