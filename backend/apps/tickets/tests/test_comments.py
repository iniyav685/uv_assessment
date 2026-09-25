"""Rich-text comments and S3 attachments (S3 is faked in-memory with moto)."""

from datetime import timedelta

import boto3
import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from moto import mock_aws

from apps.common import storage
from apps.common.richtext import html_to_text, sanitize_html
from apps.tickets.models import Attachment, AttachmentStatus
from apps.tickets.tasks import cleanup_orphan_attachments

from .helpers import raise_ac_ticket

pytestmark = pytest.mark.django_db
BUCKET = "test-attachments"


@pytest.fixture
def s3():
    with (
        mock_aws(),
        override_settings(
            AWS_STORAGE_BUCKET_NAME=BUCKET,
            AWS_S3_ENDPOINT_URL="",
            AWS_S3_PUBLIC_ENDPOINT_URL="",
            AWS_ACCESS_KEY_ID="testing",
            AWS_SECRET_ACCESS_KEY="testing",
            AWS_S3_REGION_NAME="us-east-1",
        ),
    ):
        storage.internal_client.cache_clear()
        storage.public_client.cache_clear()
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client
    storage.internal_client.cache_clear()
    storage.public_client.cache_clear()


def request_upload(api, ticket_id, **overrides):
    payload = {"filename": "photo.jpg", "content_type": "image/jpeg", "size": 1024, **overrides}
    return api.post(reverse("ticket-attachments", args=[ticket_id]), payload, format="json")


def post_comment(api, ticket_id, **payload):
    return api.post(reverse("ticket-comments", args=[ticket_id]), payload, format="json")


def test_sanitizer_keeps_formatting_and_strips_scripts():
    dirty = (
        '<p>Hi <strong>team</strong> <a href="https://x.io" onclick="steal()">link</a></p>'
        '<script>alert(1)</script><img src=x onerror="alert(1)"><a href="javascript:alert(1)">x</a>'
    )
    clean = sanitize_html(dirty)
    assert "<strong>team</strong>" in clean
    assert 'rel="noopener noreferrer nofollow"' in clean
    for bad in ("script", "onerror", "onclick", "javascript:", "<img"):
        assert bad not in clean
    assert html_to_text("<p>One</p><p>Two &amp; three</p>") == "One Two & three"


def test_upload_then_comment_with_attachment(auth_client, world, s3):
    ticket_id = raise_ac_ticket(auth_client, world)
    api = auth_client(world.client)

    res = request_upload(api, ticket_id)
    assert res.status_code == 201
    body = res.json()
    upload = body["upload"]
    assert upload["fields"]["Content-Type"] == "image/jpeg"
    assert "policy" in {k.lower() for k in upload["fields"]}

    # Simulate the browser's direct upload to the bucket.
    s3.put_object(Bucket=BUCKET, Key=upload["fields"]["key"], Body=b"x" * 2048)

    res = post_comment(
        api,
        ticket_id,
        body="<p>See <em>photo</em></p><script>x</script>",
        attachment_ids=[body["id"]],
    )
    assert res.status_code == 201
    comment = res.json()["activities"][-1]["comment"]
    assert comment["body_html"] == "<p>See <em>photo</em></p>"
    [attachment] = comment["attachments"]
    assert (attachment["name"], attachment["kind"], attachment["size"]) == (
        "photo.jpg",
        "image",
        2048,
    )
    assert "X-Amz-Signature" in attachment["url"]  # private bucket, presigned read
    assert Attachment.objects.get().status == AttachmentStatus.ATTACHED


def test_attachment_rules_are_enforced(auth_client, world, s3):
    ticket_id = raise_ac_ticket(auth_client, world)
    client = auth_client(world.client)

    assert (
        request_upload(client, ticket_id, content_type="application/x-msdownload").status_code
        == 400
    )
    assert request_upload(client, ticket_id, size=500 * 1024 * 1024).status_code == 400

    attachment_id = request_upload(client, ticket_id).json()["id"]

    # Not uploaded yet -> can't be attached.
    res = post_comment(client, ticket_id, body="<p>hi</p>", attachment_ids=[attachment_id])
    assert res.status_code == 400
    assert "not finished uploading" in res.json()["error"]["details"]["attachment_ids"][0]

    # Someone else can't attach my upload, even on a ticket they can see.
    res = post_comment(
        auth_client(world.fm), ticket_id, body="<p>hi</p>", attachment_ids=[attachment_id]
    )
    assert res.status_code == 400

    # Empty comment with no files is rejected.
    res = post_comment(client, ticket_id, body="<p> </p>")
    assert res.json()["error"]["details"]["body"]


def test_cannot_request_upload_on_invisible_ticket(auth_client, world, s3):
    ticket_id = raise_ac_ticket(auth_client, world)
    assert request_upload(auth_client(world.globex_client), ticket_id).status_code == 404


def test_orphaned_uploads_are_cleaned_up(auth_client, world, s3):
    ticket_id = raise_ac_ticket(auth_client, world)
    api = auth_client(world.client)
    old = request_upload(api, ticket_id).json()
    fresh = request_upload(api, ticket_id).json()
    s3.put_object(Bucket=BUCKET, Key=old["upload"]["fields"]["key"], Body=b"x")
    Attachment.objects.filter(pk=old["id"]).update(created_at=timezone.now() - timedelta(days=2))

    assert cleanup_orphan_attachments() == 1
    assert list(Attachment.objects.values_list("pk", flat=True)) == [
        Attachment.objects.get(pk=fresh["id"]).pk
    ]
    assert s3.list_objects_v2(Bucket=BUCKET).get("KeyCount", 0) == 0
    assert cleanup_orphan_attachments() == 0  # idempotent
