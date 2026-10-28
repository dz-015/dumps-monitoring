"""Find frames where model predicts MORE bin objects than Arseniy labeled.

Excludes ground_trash (we don't trust those metrics yet). Considers only
bin_ok (cls=0) and bin_overflow (cls=1). For each fold, runs inference with
the best.pt and reports frames where:
    n_predictions > n_gt_labels (after IoU>=0.5 matching for bins only)

These frames are candidates for label noise: model is finding bins that
Arseniy didn't annotate. Could be:
- Genuine missed labels (Arseniy needs to re-check)
- Model hallucinations (frame quality / confusion)

Saves visualizations: GT in green, model "extra" predictions in red.

Usage:
    python find_extra_predictions.py \\
        --weights runs/detect/runs/level1_tuned/level1_tuned/fold_1_seed_1/weights/best.pt \\
        --fold-dir data/folds/fold_1 \\
        --camera 2 \\
        --conf 0.5 \\
        --out-dir runs/analysis/extra_preds_cam_2
"""
from __future__ import annotations

import os
from pathlib import Path

import click


CLASS_NAMES = {0: "bin_ok", 1: "bin_overflow", 2: "ground_trash"}
BIN_CLASSES = (0, 1)


def box_iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    aarea = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    barea = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = aarea + barea - inter
    return inter / union if union > 0 else 0.0


@click.command()
@click.option("--weights", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--fold-dir", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--camera", default=None,
              help="Filter to single camera (matches cam{X}_ prefix). Default: all in fold val")
@click.option("--conf", type=float, default=0.5,
              help="Confidence threshold (high default to focus on confident extras)")
@click.option("--iou-threshold", type=float, default=0.5)
@click.option("--device", default="0")
@click.option("--out-dir", type=click.Path(path_type=Path), required=True)
@click.option("--top-n", type=int, default=30,
              help="N frames with most extras to render")
def main(weights, fold_dir, camera, conf, iou_threshold, device, out_dir, top_n):
    os.environ.setdefault("WANDB_MODE", "disabled")
    import cv2
    from ultralytics import YOLO

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    val_images_dir = fold_dir / "images" / "val"
    val_labels_dir = fold_dir / "labels" / "val"
    if camera:
        frames = sorted(val_images_dir.glob(f"cam{camera}_*.jpg"))
    else:
        frames = sorted(val_images_dir.glob("*.jpg"))
    click.echo(f"Inferencing on {len(frames)} frames at conf={conf} ...")

    model = YOLO(str(weights))

    candidates = []  # (n_extra, frame_data)
    n_total_extra = 0

    for img_path in frames:
        h, w = None, None
        # Load GT (bins only)
        lbl = val_labels_dir / (img_path.stem + ".txt")
        gts = []  # (x1,y1,x2,y2,cls) in pixels
        if lbl.exists() and lbl.stat().st_size > 0:
            img_for_size = cv2.imread(str(img_path))
            h, w = img_for_size.shape[:2]
            for line in lbl.read_text().strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split()
                cls = int(parts[0])
                if cls not in BIN_CLASSES:
                    continue
                cx, cy, w_n, h_n = map(float, parts[1:5])
                gts.append((
                    (cx - w_n / 2) * w, (cy - h_n / 2) * h,
                    (cx + w_n / 2) * w, (cy + h_n / 2) * h, cls
                ))

        results = model.predict(source=str(img_path), device=device, verbose=False,
                                save=False, conf=conf, iou=0.7)
        r = results[0]
        preds = []
        if r.boxes is not None and len(r.boxes) > 0:
            xyxy = r.boxes.xyxy.cpu().numpy()
            cls = r.boxes.cls.cpu().numpy().astype(int)
            cf = r.boxes.conf.cpu().numpy()
            for i in range(len(xyxy)):
                if int(cls[i]) not in BIN_CLASSES:
                    continue
                preds.append((float(xyxy[i, 0]), float(xyxy[i, 1]),
                              float(xyxy[i, 2]), float(xyxy[i, 3]),
                              int(cls[i]), float(cf[i])))

        # Match preds to GT (greedy, by conf)
        preds.sort(key=lambda p: -p[5])
        gt_matched = [False] * len(gts)
        extra_preds = []  # preds that don't match any GT
        for p in preds:
            best_iou, best_j = 0.0, -1
            for j, g in enumerate(gts):
                if gt_matched[j]:
                    continue
                iou = box_iou(p[:4], g[:4])
                if iou > best_iou:
                    best_iou, best_j = iou, j
            if best_j >= 0 and best_iou >= iou_threshold:
                gt_matched[best_j] = True
            else:
                extra_preds.append(p)

        if extra_preds:
            candidates.append({
                "img_path": img_path, "gts": gts, "preds": preds,
                "extra_preds": extra_preds, "n_extra": len(extra_preds),
                "n_gt": len(gts), "n_pred": len(preds),
            })
            n_total_extra += len(extra_preds)

    candidates.sort(key=lambda d: -d["n_extra"])
    click.echo(f"\n{len(candidates)} frames have extra predictions (n_pred > matched_gt).")
    click.echo(f"Total extra predictions across all frames: {n_total_extra}")
    click.echo(f"Rendering top {min(top_n, len(candidates))} ...")

    for idx, d in enumerate(candidates[:top_n]):
        img = cv2.imread(str(d["img_path"]))
        # GT in green
        for x1, y1, x2, y2, cls in d["gts"]:
            cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (50, 200, 50), 2)
            cv2.putText(img, f"GT:{CLASS_NAMES[cls]}",
                        (int(x1), max(int(y1) - 6, 14)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (50, 200, 50), 2)
        # Extra preds in red, thicker
        for x1, y1, x2, y2, cls, cf in d["extra_preds"]:
            cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (50, 50, 255), 3)
            cv2.putText(img, f"EXTRA:{CLASS_NAMES[cls]} {cf:.2f}",
                        (int(x1), int(y2) + 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (50, 50, 255), 2)
        H, W = img.shape[:2]
        cv2.putText(img,
                    f"{d['img_path'].stem}  GT={d['n_gt']} pred={d['n_pred']} extra={d['n_extra']}",
                    (10, H - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        scale = 1280 / W
        img_small = cv2.resize(img, (1280, int(H * scale)))
        out_path = out_dir / f"{d['n_extra']:02d}_{d['img_path'].stem}.jpg"
        cv2.imwrite(str(out_path), img_small, [cv2.IMWRITE_JPEG_QUALITY, 85])

    click.echo(f"Saved to {out_dir}/")


if __name__ == "__main__":
    main()
