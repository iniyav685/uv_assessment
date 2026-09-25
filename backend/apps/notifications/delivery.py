"""
E-mail channel. Two providers, selected by settings.EMAIL_PROVIDER:

  * "console" (default, local/dev/CI) — never leaves the process. Logs identifiers
    only (no addresses or ticket content) and can simulate transient failures via
    NOTIFICATION_SIMULATED_FAILURE_RATE, to exercise Celery's retry path.
  * "ses" (production) — sends real e-mail via Amazon SES using boto3, following the
    same credential pattern as apps/common/storage.py: leave the AWS key settings
    unset on AWS and boto3 uses the task's IAM role.

Either way, notifications.tasks.send_email(notification) is the single entry point
and its contract stays the same: raise TransientDeliveryError for a retryable
failure, return normally once the message has been handed off (or given up on).
"""

import logging
import random
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError
from django.conf import settings

logger = logging.getLogger(__name__)

# SES errors worth retrying: rate limits and transient service trouble. Anything
# else (e.g. MessageRejected for a malformed/unverified address) won't succeed on
# retry, so it's logged and swallowed rather than fed back into autoretry.
_RETRYABLE_SES_ERRORS = {"Throttling", "ServiceUnavailable", "RequestTimeout"}


class TransientDeliveryError(Exception):
    """A retryable failure, e.g. the mail provider timed out or throttled us."""


@lru_cache(maxsize=1)
def _ses_client():
    return boto3.client(
        "ses",
        region_name=settings.AWS_SES_REGION_NAME,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
    )


def send_email(notification) -> None:
    if settings.EMAIL_PROVIDER == "ses":
        _send_ses(notification)
    else:
        _send_console(notification)


def _send_console(notification) -> None:
    failure_rate = settings.NOTIFICATION_SIMULATED_FAILURE_RATE
    if failure_rate and random.random() < failure_rate:
        raise TransientDeliveryError("Simulated mail provider timeout")
    # Log identifiers only — no e-mail addresses or ticket content.
    logger.info(
        "notifications.email_sent provider=console notification_id=%s recipient_id=%s",
        notification.id,
        notification.recipient_id,
    )


def _send_ses(notification) -> None:
    recipient_email = notification.recipient.email
    try:
        _ses_client().send_email(
            Source=settings.EMAIL_FROM_ADDRESS,
            Destination={"ToAddresses": [recipient_email]},
            Message={
                "Subject": {"Data": f"Helpdesk — {notification.ticket.number}"},
                "Body": {"Text": {"Data": notification.message}},
            },
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in _RETRYABLE_SES_ERRORS:
            raise TransientDeliveryError(f"SES {code}") from exc
        logger.error(
            "notifications.email_failed provider=ses notification_id=%s recipient_id=%s code=%s",
            notification.id,
            notification.recipient_id,
            code,
        )
        return  # not retryable; emailed_at is still set so this isn't retried forever
    logger.info(
        "notifications.email_sent provider=ses notification_id=%s recipient_id=%s",
        notification.id,
        notification.recipient_id,
    )
