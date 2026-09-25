"""Celery notification task: fan-out, idempotency, retry and failure handling."""

from unittest import mock

import pytest
from django.test import override_settings

from apps.notifications.delivery import TransientDeliveryError
from apps.notifications.models import Notification
from apps.notifications.tasks import notify_activity
from apps.tickets.models import ActivityKind, TicketActivity
from apps.tickets.tests.helpers import act, create_ticket, raise_ac_ticket

pytestmark = pytest.mark.django_db


@pytest.fixture
def assignment_activity(auth_client, world):
    ticket_id = raise_ac_ticket(auth_client, world)
    act(auth_client(world.tech_poc), ticket_id, "assign-worker", technician_id=world.tech.id)
    return TicketActivity.objects.get(ticket_id=ticket_id, kind=ActivityKind.ASSIGNED_TECHNICIAN)


def test_api_change_enqueues_task_only_after_commit(
    auth_client, world, django_capture_on_commit_callbacks
):
    with mock.patch("apps.notifications.tasks.notify_activity.delay") as delay:
        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            raise_ac_ticket(auth_client, world, forward=False)
        delay.assert_not_called()  # nothing is sent before commit
        for callback in callbacks:
            callback()
    assert delay.call_count == 2  # "created" + "auto-assigned"


def test_notifies_stakeholders_except_actor(assignment_activity, world):
    result = notify_activity.apply(args=[assignment_activity.id]).get()

    recipients = set(
        Notification.objects.filter(activity=assignment_activity).values_list(
            "recipient__username", flat=True
        )
    )
    assert recipients == {"client.acme", "tech.prakash"}  # the POC made the change
    assert result == {"created": 2, "emailed": 2}

    messages = dict(
        Notification.objects.filter(activity=assignment_activity).values_list(
            "recipient__username", "message"
        )
    )
    number = assignment_activity.ticket.number
    assert messages["tech.prakash"].endswith(f"assigned you to #{number} AC blowing warm air")
    assert "assigned Prakash" in messages["client.acme"]


def test_duplicate_execution_is_idempotent(assignment_activity):
    with mock.patch("apps.notifications.tasks.send_email") as send:
        notify_activity.apply(args=[assignment_activity.id]).get()
        second = notify_activity.apply(args=[assignment_activity.id]).get()

    assert second == {"created": 0, "emailed": 0}
    assert Notification.objects.filter(activity=assignment_activity).count() == 2
    assert send.call_count == 2  # one e-mail per recipient, not per run


def test_transient_failure_is_retried_then_succeeds(assignment_activity):
    with mock.patch(
        "apps.notifications.tasks.send_email",
        side_effect=[TransientDeliveryError("timeout"), None, None],
    ) as send:
        result = notify_activity.apply(args=[assignment_activity.id])

    assert result.successful()
    assert send.call_count == 3
    assert not Notification.objects.filter(emailed_at__isnull=True).exists()


@override_settings(NOTIFICATION_SIMULATED_FAILURE_RATE=1.0)
def test_exhausted_retries_fail_but_keep_in_app_notifications(assignment_activity):
    result = notify_activity.apply(args=[assignment_activity.id])

    assert result.failed()
    assert isinstance(result.result, TransientDeliveryError)
    pending = Notification.objects.filter(activity=assignment_activity)
    assert pending.count() == 2  # users still see them in-app
    assert all(n.emailed_at is None for n in pending)  # e-mail can be re-driven later


def test_missing_activity_is_not_retried():
    assert notify_activity.apply(args=[999_999]).get() == {"created": 0, "emailed": 0}


def test_fully_resolved_notifies_the_offices_client_poc_to_verify(auth_client, world):
    # Raised by the FM on Acme's behalf, so the client POC is not the creator — this is the
    # case that distinguishes "notify the client POC" from "notify whoever created it".
    res = create_ticket(
        auth_client(world.fm),
        client_office_id=world.acme.id,
        title="AC down",
        issue_type_ids=[world.ac.id],
        floor_ids=[f.id for f in world.floors],
        description="Not cooling at all.",
    )
    ticket_id = res.json()["id"]
    act(auth_client(world.fm), ticket_id, "forward-to-department", department_id=world.technical.id)
    act(auth_client(world.tech_poc), ticket_id, "assign-worker", technician_id=world.tech.id)

    res = act(auth_client(world.tech), ticket_id, "submit-assessment", outcome="fully_resolved")
    assert res.json() == {"id": ticket_id, "visible": False}

    activity = TicketActivity.objects.get(ticket_id=ticket_id, kind=ActivityKind.CHANGED_STATUS)
    notify_activity.apply(args=[activity.id]).get()

    recipients = set(
        Notification.objects.filter(activity=activity).values_list(
            "recipient__username", flat=True
        )
    )
    # Creator (fm.chandan) and Department POC (poc.technical) are notified as usual; the
    # office's Client POC (client.acme) is added even though they didn't create the ticket;
    # the technician who acted, and Globex's unrelated client POC, are not notified.
    assert recipients == {"fm.chandan", "poc.technical", "client.acme"}

    message = Notification.objects.get(activity=activity, recipient__username="client.acme").message
    assert "verify" in message.lower()
