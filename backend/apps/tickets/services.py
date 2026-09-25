"""
Ticket write operations. Every state change goes through here so that:
  * the row is locked (SELECT ... FOR UPDATE) and re-checked inside a transaction,
    preventing two concurrent requests from both applying a transition;
  * the ticket update and its activity row are committed atomically;
  * notifications are enqueued only after the transaction commits.
"""

import logging
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import Role, User
from apps.common import storage
from apps.common.exceptions import InvalidStateTransition
from apps.common.richtext import html_to_text, sanitize_html, text_to_html
from apps.notifications.dispatch import enqueue_activity_notifications
from apps.organizations.models import ClientOffice, Department, Floor, IssueType

from . import policies, routing
from .models import (
    ActivityKind,
    AssessmentOutcome,
    Attachment,
    AttachmentStatus,
    Ticket,
    TicketActivity,
    TicketComment,
    TicketStatus,
)

logger = logging.getLogger(__name__)

UNASSIGNED = "Unassigned"

PERMISSION_MESSAGES = {
    "forward_to_department": "Only the concerned Facility Manager can forward this ticket.",
    "assign_worker": "Only the concerned Department POC can assign a worker.",
    "change_department": "Only the concerned Department POC can change the department.",
    "close": "Only the concerned Department POC can close this ticket.",
    "submit_assessment": "Only the assigned technician can submit an assessment.",
    "mark_resolved": "Only a Client POC of this ticket's client can mark it resolved.",
    "comment": "You cannot comment on this ticket.",
    "edit_description": "You cannot edit this ticket's description.",
}

ACTION_LABELS = {
    "forward_to_department": "forward this ticket to a department",
    "assign_worker": "assign a worker",
    "change_department": "change the department",
    "close": "close the ticket",
    "submit_assessment": "submit an assessment",
    "mark_resolved": "mark the ticket resolved",
    "comment": "comment",
    "edit_description": "edit the description",
}


def _log_activity(ticket, kind, actor=None, note="", **fields) -> TicketActivity:
    """Record an event; a plain-text `note` is stored as a linked TicketComment."""
    if note.strip():
        fields["comment"] = TicketComment.objects.create(
            ticket=ticket,
            author=actor,
            body_html=text_to_html(note),
            body_text=note.strip(),
        )
    activity = TicketActivity.objects.create(ticket=ticket, actor=actor, kind=kind, **fields)
    enqueue_activity_notifications(activity.id)
    return activity


def _lock(ticket_id: int) -> Ticket:
    return (
        Ticket.objects.select_for_update(of=("self",))
        .select_related("client_office__property")
        .get(pk=ticket_id)
    )


def _authorize(user: User, ticket: Ticket, action: str) -> None:
    if not policies.has_permission(user, ticket, action):
        raise PermissionDenied(PERMISSION_MESSAGES[action])
    if not policies.is_allowed_from(ticket, action):
        raise InvalidStateTransition(
            f"Cannot {ACTION_LABELS[action]} while the ticket is '{ticket.get_status_display()}'."
        )


def _log_transition(action, ticket, user, from_status):
    # IDs and enum values only — never descriptions, comments or personal data.
    logger.info(
        "ticket.transition action=%s ticket_id=%s user_id=%s from=%s to=%s",
        action,
        ticket.id,
        user.id,
        from_status,
        ticket.status,
    )


# --- Creation --------------------------------------------------------------


@transaction.atomic
def create_ticket(
    *,
    user: User,
    client_office: ClientOffice,
    title: str,
    issue_types: list[IssueType],
    floors: list[Floor],
    description: str,
) -> Ticket:
    """
    Issue types are tags; the first one is the primary issue and suggests the
    department the Facility Manager will forward it to. Routing starts with the FM
    of the office's location — the department POC isn't assigned (or actionable)
    until the FM forwards it; see `forward_to_department`.
    """
    primary = issue_types[0]
    department = primary.department
    location_id = client_office.property.location_id
    facility_manager = routing.facility_manager_for(location_id)
    if facility_manager is None:
        logger.warning("ticket.no_facility_manager location_id=%s", location_id)

    ticket = Ticket.objects.create(
        client_office=client_office,
        title=title,
        primary_issue_type=primary,
        description=description,
        department=department,
        facility_manager=facility_manager,
        created_by=user,
    )
    ticket.issue_types.set(issue_types)
    ticket.floors.set(floors)

    _log_activity(ticket, ActivityKind.CREATED, actor=user)
    if facility_manager:
        _log_activity(
            ticket,
            ActivityKind.AUTO_ASSIGNED,
            from_value=UNASSIGNED,
            to_value=facility_manager.display_name,
            meta={"assignee_id": facility_manager.id},
        )
    logger.info(
        "ticket.created ticket_id=%s user_id=%s department_id=%s tags=%s",
        ticket.id,
        user.id,
        department.id,
        len(issue_types),
    )
    return ticket


@transaction.atomic
def forward_to_department(*, user: User, ticket_id: int, department: Department, note: str = "") -> Ticket:
    """The Facility Manager's one action: route the ticket to a department, assigning its POC."""
    ticket = _lock(ticket_id)
    _authorize(user, ticket, "forward_to_department")

    new_poc = routing.poc_for(department)
    if new_poc is None:
        raise ValidationError({"department_id": ["This department has no POC to receive it."]})

    from_status = ticket.status
    ticket.department = department
    ticket.department_poc = new_poc
    ticket.status = TicketStatus.PENDING_TECHNICIAN_ASSIGNMENT
    ticket.save(update_fields=["department", "department_poc", "status", "updated_at"])

    _log_activity(
        ticket,
        ActivityKind.FORWARDED_TO_DEPARTMENT,
        actor=user,
        to_value=department.name,
        note=note,
        meta={"assignee_id": new_poc.id},
    )
    _log_transition("forward_to_department", ticket, user, from_status)
    return ticket


# --- Department POC actions ------------------------------------------------


@transaction.atomic
def assign_worker(*, user: User, ticket_id: int, technician: User) -> Ticket:
    ticket = _lock(ticket_id)
    _authorize(user, ticket, "assign_worker")

    if technician.role != Role.TECHNICIAN or technician.department_id != ticket.department_id:
        raise ValidationError({"technician_id": ["Select a technician from this department."]})
    if not technician.is_active:
        raise ValidationError({"technician_id": ["This technician is inactive."]})

    previous = ticket.technician
    from_status = ticket.status
    ticket.technician = technician
    ticket.assessment_outcome = ""
    ticket.status = TicketStatus.PENDING_TECHNICIAN_ASSESSMENT
    ticket.save(update_fields=["technician", "assessment_outcome", "status", "updated_at"])

    _log_activity(
        ticket,
        ActivityKind.ASSIGNED_TECHNICIAN,
        actor=user,
        from_value=previous.display_name if previous else UNASSIGNED,
        to_value=technician.display_name,
        meta={"assignee_id": technician.id},
    )
    _log_transition("assign_worker", ticket, user, from_status)
    return ticket


@transaction.atomic
def change_department(*, user: User, ticket_id: int, department: Department, note: str) -> Ticket:
    ticket = _lock(ticket_id)
    _authorize(user, ticket, "change_department")

    if department.id == ticket.department_id:
        raise ValidationError({"department_id": ["The ticket is already in this department."]})
    new_poc = routing.poc_for(department)
    if new_poc is None:
        raise ValidationError({"department_id": ["This department has no POC to receive it."]})

    old_department = ticket.department
    from_status = ticket.status
    ticket.department = department
    ticket.department_poc = new_poc
    ticket.technician = None
    ticket.assessment_outcome = ""
    ticket.status = TicketStatus.PENDING_TECHNICIAN_ASSIGNMENT
    ticket.save(
        update_fields=[
            "department",
            "department_poc",
            "technician",
            "assessment_outcome",
            "status",
            "updated_at",
        ]
    )

    _log_activity(
        ticket,
        ActivityKind.CHANGED_DEPARTMENT,
        actor=user,
        from_value=old_department.name,
        to_value=department.name,
        note=note,
        meta={"assignee_id": new_poc.id},
    )
    _log_transition("change_department", ticket, user, from_status)
    return ticket


@transaction.atomic
def close_ticket(*, user: User, ticket_id: int, note: str = "") -> Ticket:
    """The Department POC's review is done, but this doesn't fully close the ticket:
    it now waits on the Client POC's own confirmation (mark_resolved) before it does."""
    ticket = _lock(ticket_id)
    _authorize(user, ticket, "close")

    from_status = ticket.status
    ticket.status = TicketStatus.PENDING_CLIENT_CONFIRMATION
    ticket.save(update_fields=["status", "updated_at"])
    client_poc_ids = list(
        User.objects.filter(
            role=Role.CLIENT_POC, client_office_id=ticket.client_office_id
        ).values_list("id", flat=True)
    )
    _log_activity(
        ticket,
        ActivityKind.PENDING_CLIENT_CONFIRMATION,
        actor=user,
        from_value=TicketStatus(from_status).label,
        to_value=ticket.get_status_display(),
        note=note,
        meta={"client_poc_ids": client_poc_ids},
    )
    _log_transition("close", ticket, user, from_status)
    return ticket


# --- Technician action -----------------------------------------------------


@transaction.atomic
def submit_assessment(*, user: User, ticket_id: int, outcome: str, comment: str) -> Ticket:
    ticket = _lock(ticket_id)
    _authorize(user, ticket, "submit_assessment")

    if outcome != AssessmentOutcome.FULLY_RESOLVED and not comment.strip():
        raise ValidationError({"comment": ["Explain what is pending or who should take this."]})

    from_status = ticket.status
    fully_resolved = outcome == AssessmentOutcome.FULLY_RESOLVED
    ticket.assessment_outcome = outcome
    ticket.status = (
        TicketStatus.PENDING_POC_REVIEW
        if fully_resolved
        else TicketStatus.PENDING_BLOCKAGE_RESOLUTION
    )
    update_fields = ["assessment_outcome", "status", "updated_at"]
    if fully_resolved:
        # The technician's job is done; the ticket goes back to Unassigned while the
        # client verifies and the Department POC reviews.
        ticket.technician = None
        update_fields.append("technician")
    ticket.save(update_fields=update_fields)

    meta = {"outcome": outcome, "outcome_label": AssessmentOutcome(outcome).label}
    if fully_resolved:
        # Ask the client POC(s) of this specific office to verify — separate from the
        # Department POC's own review, which still happens.
        meta["client_poc_ids"] = list(
            User.objects.filter(
                role=Role.CLIENT_POC, client_office_id=ticket.client_office_id
            ).values_list("id", flat=True)
        )

    _log_activity(
        ticket,
        ActivityKind.CHANGED_STATUS,
        actor=user,
        from_value=TicketStatus(from_status).label,
        to_value=ticket.get_status_display(),
        note=comment,
        meta=meta,
    )
    _log_transition("submit_assessment", ticket, user, from_status)
    return ticket


# --- Creator / client action -----------------------------------------------


@transaction.atomic
def mark_resolved(*, user: User, ticket_id: int) -> Ticket:
    ticket = _lock(ticket_id)
    _authorize(user, ticket, "mark_resolved")
    return _close(ticket, user, TicketStatus.RESOLVED, ActivityKind.RESOLVED, "", "mark_resolved")


def _close(ticket, user, status, kind, note, action) -> Ticket:
    from_status = ticket.status
    ticket.status = status
    ticket.closed_at = timezone.now()
    ticket.closed_by = user
    ticket.save(update_fields=["status", "closed_at", "closed_by", "updated_at"])
    _log_activity(
        ticket,
        kind,
        actor=user,
        from_value=TicketStatus(from_status).label,
        to_value=ticket.get_status_display(),
        note=note,
    )
    _log_transition(action, ticket, user, from_status)
    return ticket


@transaction.atomic
def edit_description(*, user: User, ticket_id: int, description: str) -> Ticket:
    """Anyone who can comment can also correct/clarify the description while the ticket is open."""
    ticket = _lock(ticket_id)
    _authorize(user, ticket, "edit_description")

    clean_html = sanitize_html(description)
    if clean_html == ticket.description:
        return ticket

    ticket.description = clean_html
    ticket.save(update_fields=["description", "updated_at"])
    _log_activity(ticket, ActivityKind.EDITED_DESCRIPTION, actor=user)
    logger.info("ticket.description_edited ticket_id=%s user_id=%s", ticket.id, user.id)
    return ticket


# --- Comments & attachments ---------------------------------------------------


def _safe_filename(name: str) -> str:
    base = name.replace("\\", "/").rsplit("/", 1)[-1].strip() or "file"
    return "".join(c if c.isalnum() or c in "._- " else "_" for c in base)[:120]


@transaction.atomic
def request_attachment_upload(
    *, user: User, ticket_id: int, filename: str, content_type: str, size: int
) -> tuple[Attachment, dict]:
    """
    Reserve a storage key and return a presigned POST the browser uploads to
    directly. Type and size are validated here *and* pinned in the S3 policy,
    so a client can't swap the file for something else during upload.
    """
    ticket = _lock(ticket_id)
    _authorize(user, ticket, "comment")

    errors = {}
    if content_type not in settings.ATTACHMENT_ALLOWED_TYPES:
        errors["content_type"] = ["Only images, videos (MP4/WebM/MOV) and PDFs are allowed."]
    if not 0 < size <= settings.ATTACHMENT_MAX_BYTES:
        limit_mb = settings.ATTACHMENT_MAX_BYTES // (1024 * 1024)
        errors["size"] = [f"Files must be smaller than {limit_mb} MB."]
    if errors:
        raise ValidationError(errors)

    name = _safe_filename(filename)
    attachment = Attachment.objects.create(
        ticket=ticket,
        uploaded_by=user,
        storage_key=f"tickets/{ticket.pk}/{uuid.uuid4().hex}/{name}",
        original_name=name,
        content_type=content_type,
        size=size,
    )
    upload = storage.presign_upload(
        attachment.storage_key, content_type, settings.ATTACHMENT_MAX_BYTES
    )
    logger.info(
        "attachment.upload_requested attachment_id=%s ticket_id=%s user_id=%s size=%s",
        attachment.pk,
        ticket.pk,
        user.id,
        size,
    )
    return attachment, upload


@transaction.atomic
def add_comment(
    *, user: User, ticket_id: int, body_html: str, attachment_ids: list | None = None
) -> TicketActivity:
    ticket = _lock(ticket_id)
    _authorize(user, ticket, "comment")

    clean_html = sanitize_html(body_html)
    text = html_to_text(clean_html)
    attachment_ids = list(dict.fromkeys(attachment_ids or []))

    if not text and not attachment_ids:
        raise ValidationError({"body": ["Write a comment or attach a file."]})
    if len(attachment_ids) > settings.ATTACHMENTS_PER_COMMENT:
        raise ValidationError(
            {"attachment_ids": [f"Attach at most {settings.ATTACHMENTS_PER_COMMENT} files."]}
        )

    # Only the uploader's own, still-pending uploads for this ticket can be linked.
    attachments = list(
        Attachment.objects.select_for_update().filter(
            pk__in=attachment_ids,
            ticket=ticket,
            uploaded_by=user,
            status=AttachmentStatus.PENDING,
        )
    )
    if len(attachments) != len(attachment_ids):
        raise ValidationError({"attachment_ids": ["One or more attachments are invalid."]})
    for attachment in attachments:
        obj = storage.head(attachment.storage_key)
        if obj is None:
            raise ValidationError(
                {"attachment_ids": [f"'{attachment.original_name}' has not finished uploading."]}
            )
        # Trust what is actually stored, not what the client declared.
        attachment.size = obj.get("ContentLength", attachment.size)

    comment = TicketComment.objects.create(
        ticket=ticket, author=user, body_html=clean_html, body_text=text
    )
    for attachment in attachments:
        attachment.comment = comment
        attachment.status = AttachmentStatus.ATTACHED
    Attachment.objects.bulk_update(attachments, ["comment", "status", "size"])

    activity = TicketActivity.objects.create(
        ticket=ticket, actor=user, kind=ActivityKind.COMMENTED, comment=comment
    )
    enqueue_activity_notifications(activity.id)
    Ticket.objects.filter(pk=ticket.pk).update(updated_at=timezone.now())
    logger.info(
        "ticket.commented ticket_id=%s user_id=%s attachments=%s",
        ticket.id,
        user.id,
        len(attachments),
    )
    return activity
