"""Per-camera audit: pull N random frames per camera from Yandex Object Storage.

Output layout:
    <out_dir>/<camera_id>/<original_basename>.jpg
    <out_dir>/manifest.json   (so the audit is reproducible)

The S3 bucket layout is documented in memory/project_nekobak.md:
    s3://vkr-bucket-ars/cameras/{camera_id}/YYYY/MM/DD/HHMMSS.jpg

Auth: needs AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY env vars set to
Yandex IAM credentials, plus AWS_ENDPOINT_URL=https://storage.yandexcloud.net.

Run from repo root:

    AWS_ENDPOINT_URL=https://storage.yandexcloud.net \\
    AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... \\
    ./ml/venv/bin/python ml/scripts/full_camera_audit.py \\
        --bucket vkr-bucket-ars \\
        --prefix cameras \\
        --out-dir ml/data/raw/audit_2026-04-29 \\
        --frames-per-camera 30
"""

from __future__ import annotations

import json
import os
import random
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import click


@click.command()
@click.option("--bucket", type=str, required=True)
@click.option("--prefix", type=str, default="cameras")
@click.option(
    "--out-dir",
    type=click.Path(path_type=Path, file_okay=False),
    required=True,
)
@click.option("--frames-per-camera", type=int, default=30)
@click.option("--seed", type=int, default=0)
@click.option(
    "--endpoint-url",
    type=str,
    default=lambda: os.environ.get("AWS_ENDPOINT_URL", "https://storage.yandexcloud.net"),
)
def main(
    bucket: str,
    prefix: str,
    out_dir: Path,
    frames_per_camera: int,
    seed: int,
    endpoint_url: str,
) -> None:
    import boto3

    random.seed(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    s3 = boto3.client("s3", endpoint_url=endpoint_url)

    by_camera: dict[str, list[str]] = defaultdict(list)
    paginator = s3.get_paginator("list_objects_v2")
    list_prefix = prefix.rstrip("/") + "/"
    for page in paginator.paginate(Bucket=bucket, Prefix=list_prefix):
        for obj in page.get("Contents", []) or []:
            key = obj["Key"]
            if not key.endswith(".jpg"):
                continue
            relative = key[len(list_prefix):]
            parts = relative.split("/", 1)
            if len(parts) != 2:
                continue
            camera_id = parts[0]
            by_camera[camera_id].append(key)

    if not by_camera:
        raise click.ClickException(
            f"No .jpg objects found under s3://{bucket}/{list_prefix}"
        )

    manifest: dict[str, list[str]] = {}
    for camera_id, keys in sorted(by_camera.items()):
        sample_size = min(frames_per_camera, len(keys))
        sample = random.sample(keys, sample_size)
        manifest[camera_id] = sample
        cam_dir = out_dir / camera_id
        cam_dir.mkdir(parents=True, exist_ok=True)
        for key in sample:
            target = cam_dir / Path(key).name
            if target.exists():
                continue
            s3.download_file(bucket, key, str(target))
        click.echo(f"[{camera_id}] downloaded {sample_size}/{len(keys)} frames")

    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                "audit_date": datetime.now().date().isoformat(),
                "bucket": bucket,
                "prefix": prefix,
                "frames_per_camera": frames_per_camera,
                "seed": seed,
                "selected_keys": manifest,
                "total_keys_per_camera": {k: len(v) for k, v in by_camera.items()},
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    click.echo(f"\nmanifest written to {out_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
