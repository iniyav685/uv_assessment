import logging
from datetime import timedelta

from botocore.exceptions import BotoCoreError, ClientError
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.common import storage

from .models import Attachment, AttachmentStatus

logger = logging.getLogger(__name__)


@shared_task(
    autoretry_for=(BotoCoreError, ClientError),
    retry_backoff=5,
    max_retries=3,
)
def cleanup_orphan_attachments(batch_size: int = 500) -> int:
    """
    Delete uploads that were never linked to a comment (the user abandoned the
    comment, or the upload failed). Runs hourly via Celery beat.

    Safe to run concurrently or repeatedly: the row is deleted first with a
    `status=PENDING` re-check (so an attachment linked in the meantime is never
    touched), and the S3 delete runs inside the same transaction — if S3 fails,
    the row delete rolls back and the next run retries. S3 deletes are idempotent.
    """
    cutoff = timezone.now() - timedelta(hours=settings.ATTACHMENT_ORPHAN_HOURS)
    stale = list(
        Attachment.objects.filter(
            status=AttachmentStatus.PENDING, created_at__lt=cutoff
        ).values_list("pk", "storage_key")[:batch_size]
    )
    removed = 0
    for pk, key in stale:
        with transaction.atomic():
            deleted, _ = Attachment.objects.filter(pk=pk, status=AttachmentStatus.PENDING).delete()
            if deleted:
                storage.delete(key)
                removed += 1
    logger.info("attachments.cleanup removed=%s scanned=%s", removed, len(stale))
    return removed
