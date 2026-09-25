import logging
from contextlib import contextmanager

from django.db import transaction

logger = logging.getLogger(__name__)

_suppressed = False


@contextmanager
def suppress_notifications():
    """Used by bulk operations such as seeding, where notifying is noise."""
    global _suppressed
    previous, _suppressed = _suppressed, True
    try:
        yield
    finally:
        _suppressed = previous


def enqueue_activity_notifications(activity_id: int) -> None:
    """
    Schedule notification delivery after the current transaction commits, so the
    worker never sees an activity that could still be rolled back.
    """
    if _suppressed:
        return

    def _send():
        from .tasks import notify_activity

        try:
            notify_activity.delay(activity_id)
        except Exception:
            # The ticket change is already committed; a broker outage must not
            # turn a successful API call into a 500. The activity is still
            # recorded and can be re-dispatched later.
            logger.exception("notifications.enqueue_failed activity_id=%s", activity_id)

    transaction.on_commit(_send)
