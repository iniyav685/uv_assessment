"""SES e-mail delivery (SES is faked in-memory with moto)."""

from unittest import mock

import boto3
import pytest
from botocore.exceptions import ClientError
from django.test import override_settings
from moto import mock_aws

from apps.notifications import delivery
from apps.notifications.delivery import TransientDeliveryError, send_email
from apps.notifications.models import Notification
from apps.tickets.models import ActivityKind, TicketActivity
from apps.tickets.tests.helpers import act, raise_ac_ticket

pytestmark = pytest.mark.django_db


@pytest.fixture
def notification(auth_client, world):
    # Built directly via the ORM (not through notify_activity) so this stays a pure
    # test of the delivery layer, independent of EMAIL_PROVIDER at fixture time.
    ticket_id = raise_ac_ticket(auth_client, world)
    act(auth_client(world.tech_poc), ticket_id, "assign-worker", technician_id=world.tech.id)
    activity = TicketActivity.objects.get(
        ticket_id=ticket_id, kind=ActivityKind.ASSIGNED_TECHNICIAN
    )
    notif = Notification.objects.create(
        activity=activity,
        recipient=world.tech,
        ticket_id=ticket_id,
        message="You were assigned to this ticket",
    )
    return Notification.objects.select_related("recipient", "ticket").get(pk=notif.pk)


@pytest.fixture
def ses():
    with (
        mock_aws(),
        override_settings(
            EMAIL_PROVIDER="ses",
            AWS_SES_REGION_NAME="us-east-1",
            AWS_ACCESS_KEY_ID="testing",
            AWS_SECRET_ACCESS_KEY="testing",
            EMAIL_FROM_ADDRESS="helpdesk@example.com",
        ),
    ):
        delivery._ses_client.cache_clear()
        client = boto3.client("ses", region_name="us-east-1")
        yield client
    delivery._ses_client.cache_clear()


def test_send_succeeds_for_a_verified_sender(ses, notification):
    ses.verify_email_identity(EmailAddress="helpdesk@example.com")
    send_email(notification)  # no exception


def test_unverified_sender_is_logged_and_swallowed_not_retried(ses, notification):
    # SES rejects an unverified sender; that will never succeed on retry, so the
    # error is logged and swallowed instead of raising (which would trigger autoretry).
    send_email(notification)


def test_throttling_raises_transient_error_for_autoretry(notification):
    fake_client = mock.Mock()
    fake_client.send_email.side_effect = ClientError(
        {"Error": {"Code": "Throttling", "Message": "Rate exceeded"}}, "SendEmail"
    )
    with (
        override_settings(EMAIL_PROVIDER="ses"),
        mock.patch("apps.notifications.delivery._ses_client", return_value=fake_client),
        pytest.raises(TransientDeliveryError),
    ):
        send_email(notification)
