"""Compute DINOv2 ViT-B/14 embeddings for ROI crops of all camera frames.

Replaces the FiftyOne-based Stage 2 of sample_dataset.py with a direct
transformers-based pipeline. No MongoDB, no zoo daemon, just raw torch + HF.

Output: ml/data/processed/dinov2_embeddings/<cam>.npz
  arrays:
    keys      : (N,) array of S3 key strings
    timestamps: (N,) datetime strings YYYY-MM-DD_HHMMSS
    embeddings: (N, 768) float32 — DINOv2 ViT-B/14 CLS token

Run on 4090 host after prefetch:
    python scripts/compute_dinov2_embeddings.py \\
        --frames-dir data/raw/full_cameras \\
        --roi-config configs/cameras_roi.json \\
        --working-cameras 1,2,3,5,7 \\
        --out-dir data/processed/dinov2_embeddings
"""

from __future__ import annotations

import json
from pathlib import Path

import click
import numpy as np


def _key_to_local_filename_inverse(local_name: str, cam_id: str) -> str:
    """Reconstruct S3 key from local filename '2026-03-16_103439.jpg' for a given camera."""
    if "_" not in local_name:
        return ""
    date_part, time_part = local_name.split("_", 1)
    yyyy, mm, dd = date_part.split("-")
    return f"cameras/{cam_id}/{yyyy}/{mm}/{dd}/{time_part}"


@click.command()
@click.option(
    "--frames-dir",
    type=click.Path(path_type=Path, exists=True),
    default=Path("data/raw/full_cameras"),
)
@click.option(
    "--roi-config",
    type=click.Path(path_type=Path, exists=True),
    default=Path("configs/cameras_roi.json"),
)
@click.option(
    "--working-cameras",
    default="1,2,3,5,7",
)
@click.option(
    "--out-dir",
    type=click.Path(path_type=Path),
    default=Path("data/processed/dinov2_embeddings"),
)
@click.option("--model-name", default="facebook/dinov2-base")
@click.option("--batch-size", type=int, default=32)
@click.option(
    "--device",
    default="cuda",
    type=click.Choice(["cuda", "cpu"]),
)
def main(
    frames_dir: Path,
    roi_config: Path,
    working_cameras: str,
    out_dir: Path,
    model_name: str,
    batch_size: int,
    device: str,
) -> None:
    import torch
    from PIL import Image
    from transformers import AutoImageProcessor, AutoModel

    rois = json.loads(roi_config.read_text())
    cams = [c.strip() for c in working_cameras.split(",") if c.strip()]
    out_dir.mkdir(parents=True, exist_ok=True)

    if device == "cuda" and not torch.cuda.is_available():
        click.secho("CUDA not available, falling back to CPU", fg="yellow")
        device = "cpu"

    click.echo(f"Loading {model_name} ...")
    processor = AutoImageProcessor.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name).to(device).eval()
    embed_dim = model.config.hidden_size
    click.echo(f"  model loaded, embed dim = {embed_dim}, device = {device}")

    for cam in cams:
        cam_dir = frames_dir / cam
        if not cam_dir.exists():
            click.secho(f"  [{cam}] no frames dir, skipping", fg="yellow")
            continue
        if cam not in rois:
            click.secho(f"  [{cam}] no ROI defined, skipping", fg="yellow")
            continue
        roi = rois[cam]
        if not isinstance(roi, list) or len(roi) != 4:
            continue
        rx1, ry1, rx2, ry2 = roi

        frames = sorted(cam_dir.glob("*.jpg"))
        if not frames:
            click.secho(f"  [{cam}] no .jpg files, skipping", fg="yellow")
            continue

        click.echo(f"\n[{cam}] {len(frames)} frames, ROI {rx2-rx1}x{ry2-ry1}")
        keys: list[str] = []
        timestamps: list[str] = []
        embeddings = np.zeros((len(frames), embed_dim), dtype=np.float32)

        for batch_start in range(0, len(frames), batch_size):
            batch = frames[batch_start : batch_start + batch_size]
            crops = []
            for f in batch:
                with Image.open(f) as img:
                    crop = img.crop((rx1, ry1, rx2, ry2)).convert("RGB")
                crops.append(crop)
            inputs = processor(images=crops, return_tensors="pt").to(device)
            with torch.no_grad():
                outputs = model(**inputs)
            # CLS token = first token in last_hidden_state
            cls_emb = outputs.last_hidden_state[:, 0, :].cpu().numpy()
            embeddings[batch_start : batch_start + len(batch)] = cls_emb

            for f in batch:
                local_name = f.name
                stem = local_name[:-4] if local_name.endswith(".jpg") else local_name
                timestamps.append(stem)
                keys.append(_key_to_local_filename_inverse(local_name, cam))

            done = batch_start + len(batch)
            if done % (batch_size * 8) == 0 or done == len(frames):
                click.echo(f"  [{cam}] {done}/{len(frames)}")

        out_path = out_dir / f"{cam}.npz"
        np.savez_compressed(
            out_path,
            keys=np.array(keys),
            timestamps=np.array(timestamps),
            embeddings=embeddings,
        )
        click.echo(f"  [{cam}] wrote {out_path} ({embeddings.shape})")

    click.echo("\nDone. Embeddings ready for sample_dataset.py uniqueness stage.")


if __name__ == "__main__":
    main()
