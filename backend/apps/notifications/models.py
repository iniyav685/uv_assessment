from django.conf import settings
from django.db import models


class Notification(models.Model):
    """
    One row per (activity, recipient). The unique constraint is what makes the
    Celery task idempotent: a retried or duplicated task can never notify the
    same person about the same event twice.
    """

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    activity = models.ForeignKey(
        "tickets.TicketActivity", on_delete=models.CASCADE, related_name="notifications"
    )
    ticket = models.ForeignKey(
        "tickets.Ticket", on_delete=models.CASCADE, related_name="notifications"
    )
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    # Set once the (simulated) e-mail has been delivered; NULL means pending/failed.
    emailed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["activity", "recipient"], name="unique_notification_per_activity_recipient"
            ),
        ]
        indexes = [
            # Bell badge: unread count for the current user.
            models.Index(fields=["recipient", "is_read"], name="notif_recipient_unread_idx"),
        ]

    def __str__(self):
        return f"{self.recipient_id}: {self.message}"
