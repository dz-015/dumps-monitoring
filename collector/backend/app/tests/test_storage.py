from datetime import datetime, timezone

import pytest

from app.config import settings
from app.services.storage import StorageService


@pytest.fixture
def storage_service():
    service = StorageService()
    # Create bucket in local MinIO for tests (prod buckets are pre-created).
    bucket = settings.s3_snapshots_bucket
    try:
        service.client.head_bucket(Bucket=bucket)
    except Exception:
        service.client.create_bucket(Bucket=bucket)
    return service


def test_check_connection(storage_service: StorageService):
    # Should not raise when bucket exists
    storage_service.check_connection()


def test_upload_snapshot(storage_service: StorageService):
    fake_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # Minimal JPEG-like data
    now = datetime(2026, 2, 19, 12, 30, 45, tzinfo=timezone.utc)

    s3_key = storage_service.upload_snapshot(camera_id=1, timestamp=now, image_data=fake_jpeg)

    assert s3_key == "cameras/1/2026/02/19/123045.jpg"

    # Verify object actually exists in S3
    response = storage_service.client.head_object(
        Bucket=settings.s3_snapshots_bucket, Key=s3_key,
    )
    assert response["ContentLength"] == len(fake_jpeg)
    assert response["ContentType"] == "image/jpeg"

    # Cleanup
    storage_service.client.delete_object(
        Bucket=settings.s3_snapshots_bucket, Key=s3_key,
    )


def test_get_presigned_url(storage_service: StorageService):
    fake_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 50
    now = datetime(2026, 2, 19, 14, 0, 0, tzinfo=timezone.utc)
    s3_key = storage_service.upload_snapshot(camera_id=99, timestamp=now, image_data=fake_jpeg)

    url = storage_service.get_presigned_url(settings.s3_snapshots_bucket, s3_key)

    assert "cameras/99/2026/02/19/140000.jpg" in url
    assert url.startswith("http")

    # Cleanup
    storage_service.client.delete_object(
        Bucket=settings.s3_snapshots_bucket, Key=s3_key,
    )
