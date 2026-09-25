"""
Notification fan-out for a ticket activity.

Duplicate execution: tasks are acked late (see settings), so a crash can cause
redelivery, and retries re-run the whole task. Both are safe because
  1. Notification rows are created with get_or_create on the unique
     (activity, recipient) pair — a second run finds the existing rows;
  2. e-mail is only sent for rows whose `emailed_at` is still NULL, and
     `emailed_at` is set with a conditional UPDATE, so each row is e-mailed once
     even if two workers race.
"""

import logging

from celery import Task, shared_task
from django.db import OperationalError
from django.utils import timezone

from apps.tickets.models import ActivityKind, TicketActivity

from .delivery import TransientDeliveryError, send_email
from .models import Notification

logger = logging.getLogger(__name__)


def build_message(activity: TicketActivity, recipient_id: int) -> str:
    ticket = activity.ticket
    actor = activity.actor.get_full_name() if activity.actor else "System"
    ref = f"#{ticket.number} {ticket.title}"
    is_assignee = activity.meta.get("assignee_id") == recipient_id
    match activity.kind:
        case ActivityKind.AUTO_ASSIGNED:
            text = (
                f"New ticket {ref} was assigned to you"
                if is_assignee
                else f"{ref} was assigned to {activity.to_value}"
            )
        case ActivityKind.ASSIGNED_TECHNICIAN:
            text = (
                f"{actor} assigned you to {ref}"
                if is_assignee
                else f"{actor} assigned {activity.to_value} to {ref}"
            )
        case ActivityKind.FORWARDED_TO_DEPARTMENT:
            text = (
                f"{ref} was forwarded to your department"
                if is_assignee
                else f"{actor} forwarded {ref} to {activity.to_value}"
            )
        case ActivityKind.CHANGED_DEPARTMENT:
            text = (
                f"{ref} was forwarded to your department"
                if is_assignee
                else f"{actor} moved {ref} to {activity.to_value}"
            )
        case ActivityKind.CHANGED_STATUS:
            text = (
                f"{actor} marked {ref} fully resolved. Please verify and mark it resolved "
                "if you're satisfied."
                if recipient_id in activity.meta.get("client_poc_ids", ())
                else f"{actor} submitted an assessment on {ref}"
            )
        case ActivityKind.PENDING_CLIENT_CONFIRMATION:
            text = (
                f"{actor} marked {ref} resolved. Please confirm to close it."
                if recipient_id in activity.meta.get("client_poc_ids", ())
                else f"{actor} marked {ref} resolved, pending client confirmation"
            )
        case ActivityKind.RESOLVED:
            text = f"{actor} marked {ref} resolved"
        case ActivityKind.CLOSED:
            text = f"{actor} closed {ref}"
        case ActivityKind.EDITED_DESCRIPTION:
            text = f"{actor} edited the description of {ref}"
        case _:
            text = f"{actor} commented on {ref}"
    return text[:255]


def recipients_for(activity: TicketActivity) -> set[int]:
    """Stakeholders of the ticket after the change, minus whoever made it."""
    if activity.kind == ActivityKind.CREATED:
        return set()  # the paired "auto-assigned" event already notifies everyone
    ticket = activity.ticket
    ids = {ticket.created_by_id, ticket.department_poc_id, ticket.technician_id}
    # The Facility Manager monitors their location: new tickets and closures only.
    if activity.kind in (ActivityKind.AUTO_ASSIGNED, ActivityKind.RESOLVED, ActivityKind.CLOSED):
        ids.add(ticket.facility_manager_id)
    # Fully resolved: the client POC(s) of this office, asked to verify (set by the service).
    ids.update(activity.meta.get("client_poc_ids", ()))
    ids.discard(None)
    if activity.actor_id:
        ids.discard(activity.actor_id)
    return ids


class NotificationTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        # Retries exhausted. In-app notifications already exist; only e-mail is
        # missing and can be re-driven by re-running the task for this activity.
        logger.error(
            "notifications.task_failed task_id=%s args=%s error=%s",
            task_id,
            args,
            type(exc).__name__,
        )


@shared_task(
    bind=True,
    base=NotificationTask,
    autoretry_for=(TransientDeliveryError, OperationalError),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=4,
)
def notify_activity(self, activity_id: int) -> dict:
    try:
        activity = TicketActivity.objects.select_related("ticket", "actor").get(pk=activity_id)
    except TicketActivity.DoesNotExist:
        # Not retryable: the activity was deleted (or never committed).
        logger.warning("notifications.activity_missing activity_id=%s", activity_id)
        return {"created": 0, "emailed": 0}

    created = 0
    for recipient_id in recipients_for(activity):
        _, was_created = Notification.objects.get_or_create(
            activity=activity,
            recipient_id=recipient_id,
            defaults={
                "ticket_id": activity.ticket_id,
                "message": build_message(activity, recipient_id),
            },
        )
        created += was_created

    emailed = 0
    pending = Notification.objects.filter(
        activity=activity, emailed_at__isnull=True
    ).select_related("recipient", "ticket")
    for notification in pending:
        send_email(notification)  # may raise TransientDeliveryError -> autoretry
        emailed += Notification.objects.filter(pk=notification.pk, emailed_at__isnull=True).update(
            emailed_at=timezone.now()
        )

    logger.info(
        "notifications.processed activity_id=%s created=%s emailed=%s attempt=%s",
        activity_id,
        created,
        emailed,
        self.request.retries,
    )
    return {"created": created, "emailed": emailed}
