"""Hybrid sampling pipeline: select N frames from raw S3 capture for labeling.

Per Q4 (plan v1.4):
  Stage 1 (30%): detector-guided — COCO YOLOv8m on full frames, score by detections inside ROI.
  Stage 2 (60%): DINOv2 uniqueness on ROI crops, per-camera stratified.
  Stage 3 (10%): temporal random per camera-day.

ROI definitions read from ml/configs/cameras_roi.json: {camera_id: [x1, y1, x2, y2]} in pixel coords.

Run from repo root after `pip install` and after audit:

    AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... \\
    ./ml/venv/bin/python ml/scripts/sample_dataset.py \\
        --bucket vkr-bucket-ars \\
        --prefix cameras \\
        --roi-config ml/configs/cameras_roi.json \\
        --working-cameras 1,2,3,5,7 \\
        --total-budget 1500 \\
        --out-dir ml/data/processed/to_label
"""

from __future__ import annotations

import json
import os
import random
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import click


def _key_to_camera_and_timestamp(key: str, prefix: str) -> tuple[str, datetime] | None:
    """Parse 'cameras/{cam}/YYYY/MM/DD/HHMMSS.jpg' to (camera, datetime). None if malformed."""
    rel = key[len(prefix.rstrip("/") + "/") :]
    parts = rel.split("/")
    if len(parts) != 5 or not parts[4].endswith(".jpg"):
        return None
    cam, yyyy, mm, dd, fname = parts
    hms = fname[:6]
    try:
        ts = datetime.strptime(f"{yyyy}{mm}{dd}{hms}", "%Y%m%d%H%M%S")
    except ValueError:
        return None
    return cam, ts


def _key_to_local_filename(key: str) -> str:
    """Encode date+time in filename to avoid HHMMSS-only collisions across days.

    'cameras/3/2026/03/16/103439.jpg' → '2026-03-16_103439.jpg'
    """
    parts = key.split("/")
    if len(parts) >= 5:
        yyyy, mm, dd, fname = parts[-4], parts[-3], parts[-2], parts[-1]
        return f"{yyyy}-{mm}-{dd}_{fname}"
    return Path(key).name  # fallback


def list_camera_keys(s3, bucket: str, prefix: str, working_cameras: set[str]) -> dict[str, list[tuple[str, datetime]]]:
    """List all .jpg keys per working camera, parsed with timestamps."""
    paginator = s3.get_paginator("list_objects_v2")
    by_cam: dict[str, list[tuple[str, datetime]]] = defaultdict(list)
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix.rstrip("/") + "/"):
        for obj in page.get("Contents") or []:
            key = obj["Key"]
            parsed = _key_to_camera_and_timestamp(key, prefix)
            if parsed is None:
                continue
            cam, ts = parsed
            if cam in working_cameras:
                by_cam[cam].append((key, ts))
    return by_cam


def stage1_detector_guided(
    s3,
    bucket: str,
    candidates: list[tuple[str, datetime]],
    roi: tuple[int, int, int, int],
    yolo_model,
    budget: int,
    cache_dir: Path,
    conf: float = 0.15,
    imgsz: int = 1280,
) -> list[str]:
    """Score frames by COCO detections inside ROI; return top-N keys.

    Detections of bin-related COCO classes ('bottle', 'cup', 'bowl', 'vase', 'suitcase',
    'refrigerator') inside or overlapping the ROI count toward the score. Plus any
    detection touching the ROI bounding box.
    """
    BIN_PROXY_CLASSES = {"bottle", "cup", "bowl", "vase", "suitcase", "refrigerator"}
    rx1, ry1, rx2, ry2 = roi

    cache_dir.mkdir(parents=True, exist_ok=True)
    scores: list[tuple[float, str]] = []

    for key, _ts in candidates:
        local = cache_dir / _key_to_local_filename(key)
        if not local.exists():
            s3.download_file(bucket, key, str(local))
        result = yolo_model.predict(source=str(local), conf=conf, imgsz=imgsz, verbose=False)[0]
        score = 0.0
        if result.boxes is not None and len(result.boxes):
            for cls_idx, xyxy in zip(result.boxes.cls.int().tolist(), result.boxes.xyxy.tolist()):
                cls_name = result.names[cls_idx]
                bx1, by1, bx2, by2 = xyxy
                inter_x1, inter_y1 = max(bx1, rx1), max(by1, ry1)
                inter_x2, inter_y2 = min(bx2, rx2), min(by2, ry2)
                overlap = max(0.0, inter_x2 - inter_x1) * max(0.0, inter_y2 - inter_y1)
                if overlap == 0:
                    continue
                bbox_area = max(1.0, (bx2 - bx1) * (by2 - by1))
                in_roi_ratio = overlap / bbox_area
                weight = 2.0 if cls_name in BIN_PROXY_CLASSES else 0.5
                score += weight * in_roi_ratio
        scores.append((score, key))

    scores.sort(reverse=True)
    return [key for score, key in scores[:budget] if score > 0]


def stage2_dinov2_uniqueness(
    candidates: list[tuple[str, datetime]],
    embeddings_path: Path,
    budget: int,
    k_neighbors: int = 10,
) -> list[str]:
    """DINOv2 uniqueness ranking from pre-computed embeddings.

    Replaces the FiftyOne-based implementation with direct numpy. Algorithm follows
    FiftyOne Brain `compute_uniqueness` methodology: for each frame, score is the
    mean COSINE distance to its k nearest neighbours within the same camera. High
    score = high uniqueness = picked first.

    embeddings_path is a .npz file produced by scripts/compute_dinov2_embeddings.py
    containing arrays: keys, timestamps, embeddings (N, D).
    """
    import numpy as np

    if not embeddings_path.exists():
        raise FileNotFoundError(
            f"DINOv2 embeddings not found at {embeddings_path}. "
            "Run scripts/compute_dinov2_embeddings.py first."
        )

    data = np.load(embeddings_path, allow_pickle=False)
    cached_keys = data["keys"].astype(str)
    cached_emb = data["embeddings"]
    key_to_idx = {k: i for i, k in enumerate(cached_keys)}

    # Restrict to candidate frames present in cache
    cand_indices = []
    cand_keys = []
    for key, _ts in candidates:
        idx = key_to_idx.get(key)
        if idx is not None:
            cand_indices.append(idx)
            cand_keys.append(key)
    if len(cand_indices) == 0:
        return []
    if len(cand_indices) <= budget:
        return cand_keys

    # Cosine similarity matrix → distance → mean k-NN distance
    emb = cached_emb[cand_indices].astype(np.float32)
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-8)
    emb_norm = emb / norms
    sim = emb_norm @ emb_norm.T  # (N, N) cosine similarity in [-1, 1]
    np.fill_diagonal(sim, -np.inf)  # exclude self
    # k nearest neighbours = highest similarity → smallest distance
    k = min(k_neighbors, len(cand_indices) - 1)
    top_k_sim = np.partition(sim, -k, axis=1)[:, -k:]
    mean_top_k_sim = top_k_sim.mean(axis=1)
    # uniqueness = 1 - mean_top_k_similarity (high → frame is novel)
    uniqueness = 1.0 - mean_top_k_sim

    order = np.argsort(-uniqueness)  # desc
    picked = order[:budget]
    return [cand_keys[i] for i in picked]


def stage3_temporal_random(
    candidates: list[tuple[str, datetime]],
    budget: int,
    rng: random.Random,
) -> list[str]:
    """Stratified-by-day random sample as insurance against embedding pathologies."""
    by_day: dict[str, list[str]] = defaultdict(list)
    for key, ts in candidates:
        by_day[ts.date().isoformat()].append(key)

    days = sorted(by_day)
    per_day = max(1, budget // max(1, len(days)))
    picked: list[str] = []
    for day in days:
        sample = rng.sample(by_day[day], min(per_day, len(by_day[day])))
        picked.extend(sample)
    rng.shuffle(picked)
    return picked[:budget]


def download_selected(s3, bucket: str, keys: list[str], out_dir: Path) -> None:
    """Materialize selected frames to out_dir/{date_basename}."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for key in keys:
        target = out_dir / _key_to_local_filename(key)
        if not target.exists():
            s3.download_file(bucket, key, str(target))


@click.command()
@click.option("--bucket", required=True)
@click.option("--prefix", default="cameras")
@click.option(
    "--roi-config",
    type=click.Path(path_type=Path, exists=True),
    required=True,
    help="JSON: {camera_id: [x1,y1,x2,y2]}",
)
@click.option(
    "--working-cameras",
    required=True,
    help="Comma-separated working camera IDs (e.g. '1,2,3,5,7')",
)
@click.option("--total-budget", type=int, default=1500)
@click.option(
    "--detector-share", type=float, default=0.30, help="Fraction of budget for Stage 1"
)
@click.option(
    "--uniqueness-share",
    type=float,
    default=0.60,
    help="Fraction of budget for Stage 2 (DINOv2 uniqueness). 0 disables; otherwise embeddings-dir must exist.",
)
@click.option(
    "--embeddings-dir",
    type=click.Path(path_type=Path),
    default=Path("data/processed/dinov2_embeddings"),
    help="Directory with per-camera .npz files from compute_dinov2_embeddings.py",
)
@click.option(
    "--out-dir",
    type=click.Path(path_type=Path),
    default=Path("ml/data/processed/to_label"),
)
@click.option(
    "--cache-dir",
    type=click.Path(path_type=Path),
    default=Path("ml/data/processed/_full_cache"),
    help="Where to cache downloaded frames + crops between stages.",
)
@click.option("--seed", type=int, default=0)
@click.option(
    "--endpoint-url",
    default=lambda: os.environ.get("AWS_ENDPOINT_URL", "https://storage.yandexcloud.net"),
)
def main(
    bucket: str,
    prefix: str,
    roi_config: Path,
    working_cameras: str,
    total_budget: int,
    detector_share: float,
    uniqueness_share: float,
    embeddings_dir: Path,
    out_dir: Path,
    cache_dir: Path,
    seed: int,
    endpoint_url: str,
) -> None:
    import boto3
    from ultralytics import YOLO

    rois = json.loads(roi_config.read_text())
    cams = [c.strip() for c in working_cameras.split(",") if c.strip()]
    missing_rois = [c for c in cams if c not in rois]
    if missing_rois:
        raise click.ClickException(f"ROI not defined for cameras: {missing_rois}")

    rng = random.Random(seed)
    s3 = boto3.client("s3", endpoint_url=endpoint_url)
    yolo = YOLO("yolov8m.pt")

    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    by_cam = list_camera_keys(s3, bucket, prefix, set(cams))
    click.echo("Frames per camera in S3:")
    for cam in cams:
        click.echo(f"  {cam}: {len(by_cam.get(cam, []))} frames")

    per_cam_budget = total_budget // len(cams)
    s1_per_cam = int(per_cam_budget * detector_share)
    s2_per_cam = int(per_cam_budget * uniqueness_share)
    s3_per_cam = per_cam_budget - s1_per_cam - s2_per_cam

    click.echo(
        f"\nPer-camera budget: {per_cam_budget} = {s1_per_cam}(detector) + "
        f"{s2_per_cam}(uniqueness) + {s3_per_cam}(temporal)"
    )

    selected_per_cam: dict[str, list[str]] = {}
    for cam in cams:
        candidates = sorted(by_cam.get(cam, []), key=lambda kt: kt[1])
        if not candidates:
            click.secho(f"  [{cam}] no frames in S3, skipping", fg="yellow")
            continue
        roi = tuple(rois[cam])
        cam_cache = cache_dir / cam
        click.echo(f"\n[{cam}] Stage 1 (detector-guided)…")
        s1_keys = stage1_detector_guided(s3, bucket, candidates, roi, yolo, s1_per_cam, cam_cache)
        click.echo(f"  picked {len(s1_keys)}")

        if s2_per_cam > 0:
            remaining_after_s1 = [(k, t) for k, t in candidates if k not in set(s1_keys)]
            click.echo(f"[{cam}] Stage 2 (DINOv2 uniqueness, k=10 cosine)…")
            embed_path = embeddings_dir / f"{cam}.npz"
            s2_keys = stage2_dinov2_uniqueness(remaining_after_s1, embed_path, s2_per_cam)
            click.echo(f"  picked {len(s2_keys)}")
        else:
            s2_keys = []
            click.echo(f"[{cam}] Stage 2 disabled (uniqueness-share=0)")

        already = set(s1_keys) | set(s2_keys)
        remaining_after_s2 = [(k, t) for k, t in candidates if k not in already]
        click.echo(f"[{cam}] Stage 3 (temporal random)…")
        s3_keys = stage3_temporal_random(remaining_after_s2, s3_per_cam, rng)
        click.echo(f"  picked {len(s3_keys)}")

        selected_per_cam[cam] = s1_keys + s2_keys + s3_keys

    cam_out = lambda cam: out_dir / cam
    for cam, keys in selected_per_cam.items():
        download_selected(s3, bucket, keys, cam_out(cam))

    manifest = {
        "selection_date": datetime.now().date().isoformat(),
        "bucket": bucket,
        "prefix": prefix,
        "total_budget": total_budget,
        "shares": {
            "detector": detector_share,
            "uniqueness": uniqueness_share,
            "temporal": round(1 - detector_share - uniqueness_share, 2),
        },
        "rois_used": {c: rois[c] for c in cams},
        "seed": seed,
        "selected_per_camera": selected_per_cam,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    click.echo(f"\nmanifest written to {out_dir / 'manifest.json'}")
    total_selected = sum(len(v) for v in selected_per_cam.values())
    click.echo(f"Total selected: {total_selected} (target: {total_budget})")

    if cache_dir.exists():
        size_mb = sum(f.stat().st_size for f in cache_dir.rglob("*") if f.is_file()) / 1e6
        click.echo(f"Cache size: {size_mb:.0f} MB at {cache_dir}. Safe to delete after labeling start.")


if __name__ == "__main__":
    main()
