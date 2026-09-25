"""
Create the attachments bucket (private) with CORS for browser uploads.
Idempotent; used for local S3 emulators. On AWS the bucket is provisioned by IaC.
"""

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.common import storage


class Command(BaseCommand):
    help = "Ensure the attachments bucket exists with CORS for the frontend origin."

    def handle(self, *args, **options):
        client = storage.internal_client()
        name = storage.bucket()
        try:
            client.head_bucket(Bucket=name)
            self.stdout.write(f"Bucket '{name}' exists.")
        except ClientError:
            client.create_bucket(Bucket=name)
            self.stdout.write(self.style.SUCCESS(f"Created bucket '{name}'."))

        try:
            client.put_bucket_cors(
                Bucket=name,
                CORSConfiguration={
                    "CORSRules": [
                        {
                            "AllowedOrigins": settings.CORS_ALLOWED_ORIGINS,
                            "AllowedMethods": ["GET", "POST"],
                            "AllowedHeaders": ["*"],
                            "MaxAgeSeconds": 3600,
                        }
                    ]
                },
            )
        except ClientError as exc:  # some emulators don't implement bucket CORS
            self.stdout.write(f"Skipping bucket CORS: {exc.response['Error'].get('Code')}")
