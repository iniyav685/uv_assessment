"""Simulated e-mail channel. Swap for SES/SendGrid in production."""

import logging
import random

from django.conf import settings

logger = logging.getLogger(__name__)


class TransientDeliveryError(Exception):
    """A retryable failure, e.g. the mail provider timed out."""


def send_email(notification) -> None:
    failure_rate = settings.NOTIFICATION_SIMULATED_FAILURE_RATE
    if failure_rate and random.random() < failure_rate:
        raise TransientDeliveryError("Simulated mail provider timeout")
    # Log identifiers only — no e-mail addresses or ticket content.
    logger.info(
        "notifications.email_sent notification_id=%s recipient_id=%s",
        notification.id,
        notification.recipient_id,
    )
