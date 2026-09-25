"""Celery notification task: fan-out, idempotency, retry and failure handling."""

from unittest import mock

import pytest
from django.test import override_settings

from apps.accounts.models import Role
from apps.notifications.delivery import TransientDeliveryError
from apps.notifications.models import Notification
from apps.notifications.tasks import notify_activity, recipients_for
from apps.tickets import services
from apps.tickets.models import ActivityKind, TicketActivity
from apps.tickets.tests.helpers import act, create_ticket, raise_ac_ticket
from conftest import make_user

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


def test_reassignment_before_the_first_notification_runs_still_targets_the_original_technician(
    world,
):
    """The notification queue gives no ordering/timing guarantee: if a technician is
    reassigned again before the *first* assignment's notify task runs (a real race
    once the queue has any backlog), recipients_for() must still resolve to the
    technician that specific activity was about — not whoever currently holds the
    ticket, which by then is someone else entirely."""
    other_tech = make_user("tech.ravi", Role.TECHNICIAN, department=world.technical)

    # Built directly via the service layer (not through HTTP) so this stays a pure
    # service/notification test.
    ticket = services.create_ticket(
        user=world.client,
        client_office=world.acme,
        title="AC blowing warm air",
        issue_types=[world.ac],
        floors=world.floors,
        description="",
    )
    services.forward_to_department(user=world.fm, ticket_id=ticket.id, department=world.technical)
    services.assign_worker(user=world.tech_poc, ticket_id=ticket.id, technician=world.tech)
    first_activity = TicketActivity.objects.get(
        ticket_id=ticket.id, kind=ActivityKind.ASSIGNED_TECHNICIAN
    )

    # Superseded before the first activity's notification task ever runs.
    services.assign_worker(user=world.tech_poc, ticket_id=ticket.id, technician=other_tech)

    recipients = recipients_for(first_activity)
    assert world.tech.id in recipients
    assert other_tech.id not in recipients

    result = notify_activity.apply(args=[first_activity.id]).get()
    assert result["created"] == len(recipients)
    message = Notification.objects.get(activity=first_activity, recipient=world.tech).message
    assert "assigned you" in message


def test_reroute_before_the_first_notification_runs_still_targets_the_original_poc(world):
    """Same race, for department routing: change_department overwrites department_poc
    before the *first* forward's notification runs. recipients_for() must resolve to
    the POC that specific FORWARDED_TO_DEPARTMENT activity actually routed to."""
    ticket = services.create_ticket(
        user=world.client,
        client_office=world.acme,
        title="AC blowing warm air",
        issue_types=[world.ac],
        floors=world.floors,
        description="",
    )
    services.forward_to_department(user=world.fm, ticket_id=ticket.id, department=world.technical)
    forward_activity = TicketActivity.objects.get(
        ticket_id=ticket.id, kind=ActivityKind.FORWARDED_TO_DEPARTMENT
    )

    # Rerouted to a different department before the forward's notification task runs.
    services.change_department(
        user=world.tech_poc, ticket_id=ticket.id, department=world.it, note="Wrong department"
    )

    recipients = recipients_for(forward_activity)
    assert world.tech_poc.id in recipients
    assert world.it_poc.id not in recipients


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
