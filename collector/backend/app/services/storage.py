import logging
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """S3-compatible storage operations (MinIO / Yandex Object Storage)."""

    def __init__(self):
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )

    def check_connection(self):
        """Verify S3 credentials and bucket access on startup."""
        bucket = settings.s3_snapshots_bucket
        try:
            self.client.head_bucket(Bucket=bucket)
            logger.info("S3 bucket OK: %s", bucket)
        except ClientError as e:
            code = e.response["Error"].get("Code", "")
            logger.warning(
                "Cannot access S3 bucket %s (code=%s). "
                "Uploads may fail — check credentials and bucket permissions.",
                bucket, code,
            )

    def upload_snapshot(
        self, camera_id: int, timestamp: datetime, image_data: bytes
    ) -> str:
        """Upload JPEG to S3. Returns s3_key."""
        s3_key = f"cameras/{camera_id}/{timestamp.strftime('%Y/%m/%d/%H%M%S')}.jpg"
        self.client.put_object(
            Bucket=settings.s3_snapshots_bucket,
            Key=s3_key,
            Body=image_data,
            ContentType="image/jpeg",
        )
        return s3_key

    def get_presigned_url(
        self,
        bucket: str,
        key: str,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        """Generate presigned URL for downloading."""
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=int(expires.total_seconds()),
        )


storage = StorageService()
