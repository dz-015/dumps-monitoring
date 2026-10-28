"""Pre-download all S3 frames for selected cameras to local cache.

So that morning sample_dataset.py runs without S3 round-trips per frame (slow).

Run with credentials in env:

    AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... \\
    python scripts/prefetch_camera_frames.py \\
        --bucket vkr-bucket-ars --prefix cameras \\
        --cameras 1,2,3,4,5,6,7 \\
        --out-dir data/raw/full_cameras
"""

from __future__ import annotations

import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import click


@click.command()
@click.option("--bucket", required=True)
@click.option("--prefix", default="cameras")
@click.option("--cameras", required=True, help="Comma-separated camera ids, e.g. '1,2,3,7'")
@click.option(
    "--out-dir",
    type=click.Path(path_type=Path),
    default=Path("data/raw/full_cameras"),
)
@click.option(
    "--endpoint-url",
    default=lambda: os.environ.get("AWS_ENDPOINT_URL", "https://storage.yandexcloud.net"),
)
@click.option("--max-workers", type=int, default=16)
def main(bucket: str, prefix: str, cameras: str, out_dir: Path, endpoint_url: str, max_workers: int) -> None:
    import boto3
    from botocore.config import Config

    cams = [c.strip() for c in cameras.split(",") if c.strip()]
    out_dir.mkdir(parents=True, exist_ok=True)

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        config=Config(max_pool_connections=max(max_workers * 2, 32)),
    )

    keys_by_cam: dict[str, list[str]] = defaultdict(list)
    paginator = s3.get_paginator("list_objects_v2")
    # Per-camera prefix listing: more reliable on Yandex S3 than global prefix scan,
    # avoids paginator quirks where global iteration returns only first page.
    for cam in cams:
        cam_prefix = f"{prefix.rstrip('/')}/{cam}/"
        page_iter = paginator.paginate(
            Bucket=bucket, Prefix=cam_prefix, PaginationConfig={"PageSize": 1000}
        )
        for page in page_iter:
            for obj in page.get("Contents") or []:
                key = obj["Key"]
                if key.endswith(".jpg"):
                    keys_by_cam[cam].append(key)

    total = sum(len(v) for v in keys_by_cam.values())
    click.echo(f"Total keys to fetch: {total}")
    for cam in cams:
        click.echo(f"  cam {cam}: {len(keys_by_cam.get(cam, []))} keys")

    def download_one(key: str) -> tuple[str, bool]:
        # key looks like: cameras/{cam}/YYYY/MM/DD/HHMMSS.jpg
        rel = key[len(prefix.rstrip("/") + "/") :]
        parts = rel.split("/")
        if len(parts) != 5:
            return key, False
        cam, yyyy, mm, dd, fname = parts
        target_dir = out_dir / cam
        target_dir.mkdir(parents=True, exist_ok=True)
        # Encode full date in filename to avoid same-HHMMSS collisions across days
        target = target_dir / f"{yyyy}-{mm}-{dd}_{fname}"
        if target.exists() and target.stat().st_size > 1024:
            return key, True
        try:
            s3.download_file(bucket, key, str(target))
            return key, True
        except Exception as e:
            click.secho(f"  failed {key}: {e}", fg="red")
            return key, False

    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(download_one, key): key for cam in cams for key in keys_by_cam.get(cam, [])}
        for fut in as_completed(futures):
            completed += 1
            if completed % 100 == 0:
                click.echo(f"  {completed}/{total}")

    click.echo(f"\nFetched {total} frames to {out_dir}")
    size_mb = sum(f.stat().st_size for f in out_dir.rglob("*.jpg")) / 1e6
    click.echo(f"Total size: {size_mb:.0f} MB")


if __name__ == "__main__":
    main()
