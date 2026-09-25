"""
Thin wrapper over S3 (MinIO locally) for private, presigned file access.

Two endpoints exist because presigned URLs embed the host they were signed for:
  * AWS_S3_ENDPOINT_URL        — how the backend reaches storage (e.g. http://minio:9000)
  * AWS_S3_PUBLIC_ENDPOINT_URL — how the browser reaches it   (e.g. http://localhost:9000)
On AWS both are unset and boto3 uses the regional S3 endpoint with the task's IAM role.
"""

from functools import lru_cache

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from django.conf import settings


def _client(endpoint_url):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url or None,
        region_name=settings.AWS_S3_REGION_NAME,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


@lru_cache(maxsize=1)
def internal_client():
    return _client(settings.AWS_S3_ENDPOINT_URL)


@lru_cache(maxsize=1)
def public_client():
    return _client(settings.AWS_S3_PUBLIC_ENDPOINT_URL or settings.AWS_S3_ENDPOINT_URL)


def bucket() -> str:
    return settings.AWS_STORAGE_BUCKET_NAME


def presign_upload(key: str, content_type: str, max_bytes: int) -> dict:
    """Presigned POST: the policy pins the key, content type and maximum size."""
    return public_client().generate_presigned_post(
        Bucket=bucket(),
        Key=key,
        Fields={"Content-Type": content_type},
        Conditions=[
            {"Content-Type": content_type},
            ["content-length-range", 1, max_bytes],
        ],
        ExpiresIn=settings.ATTACHMENT_UPLOAD_URL_TTL,
    )


def presign_download(key: str, filename: str, inline: bool) -> str:
    disposition = "inline" if inline else "attachment"
    safe_name = filename.replace('"', "")
    return public_client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket(),
            "Key": key,
            "ResponseContentDisposition": f'{disposition}; filename="{safe_name}"',
        },
        ExpiresIn=settings.ATTACHMENT_DOWNLOAD_URL_TTL,
    )


def head(key: str) -> dict | None:
    """Object metadata, or None if it doesn't exist (i.e. the upload never happened)."""
    try:
        return internal_client().head_object(Bucket=bucket(), Key=key)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
            return None
        raise


def delete(key: str) -> None:
    # S3 DeleteObject is idempotent: deleting a missing key succeeds.
    internal_client().delete_object(Bucket=bucket(), Key=key)
