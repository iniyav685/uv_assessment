import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.common.models import TimeStampedModel


class TicketStatus(models.TextChoices):
    PENDING_FACILITY_MANAGER_REVIEW = (
        "pending_facility_manager_review",
        "Pending Facility Manager Review",
    )
    PENDING_TECHNICIAN_ASSIGNMENT = "pending_technician_assignment", "Pending Technician Assignment"
    PENDING_TECHNICIAN_ASSESSMENT = "pending_technician_assessment", "Pending Technician Assessment"
    PENDING_POC_REVIEW = "pending_poc_review", "Pending Department POC Review"
    PENDING_BLOCKAGE_RESOLUTION = "pending_blockage_resolution", "Pending Blockage Resolution"
    # The Department POC has reviewed and signed off, but the ticket isn't fully
    # closed yet: the Client POC still has to confirm (mark_resolved) before it does.
    PENDING_CLIENT_CONFIRMATION = "pending_client_confirmation", "Pending Client Confirmation"
    RESOLVED = "resolved", "Resolved"
    CLOSED = "closed", "Closed"


OPEN_STATUSES = frozenset(
    {
        TicketStatus.PENDING_FACILITY_MANAGER_REVIEW,
        TicketStatus.PENDING_TECHNICIAN_ASSIGNMENT,
        TicketStatus.PENDING_TECHNICIAN_ASSESSMENT,
        TicketStatus.PENDING_POC_REVIEW,
        TicketStatus.PENDING_BLOCKAGE_RESOLUTION,
        TicketStatus.PENDING_CLIENT_CONFIRMATION,
    }
)
CLOSED_STATUSES = frozenset({TicketStatus.RESOLVED, TicketStatus.CLOSED})


class AssessmentOutcome(models.TextChoices):
    FULLY_RESOLVED = "fully_resolved", "Fully Resolved"
    PARTIALLY_RESOLVED = "partially_resolved", "Partially Resolved"
    NEEDS_REASSIGNMENT = "needs_reassignment", "Department/Worker Change Suggested"


TICKET_NUMBER_OFFSET = 1000


class Ticket(TimeStampedModel):
    client_office = models.ForeignKey(
        "organizations.ClientOffice", on_delete=models.PROTECT, related_name="tickets"
    )
    title = models.CharField(max_length=150)
    # Issue types are tags (many per ticket). The first one the user picked is the
    # primary issue: it decides the department the ticket is routed to.
    issue_types = models.ManyToManyField(
        "organizations.IssueType", related_name="tickets", help_text="Issue tags."
    )
    primary_issue_type = models.ForeignKey(
        "organizations.IssueType", on_delete=models.PROTECT, related_name="primary_tickets"
    )
    description = models.TextField(blank=True)
    floors = models.ManyToManyField("organizations.Floor", related_name="tickets", blank=True)

    # Current routing. `department` changes on "Change Department"; `department_poc` is the POC
    # snapshot at routing time so reassigning a department's POC doesn't silently move tickets.
    department = models.ForeignKey(
        "organizations.Department", on_delete=models.PROTECT, related_name="tickets"
    )
    department_poc = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="poc_tickets",
    )
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="technician_tickets",
    )
    # The "concerned" FM: auto-linked at creation to the FM of the office's location.
    # Stored (not derived) so a later FM change doesn't silently move old tickets.
    facility_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="facility_manager_tickets",
    )

    status = models.CharField(
        max_length=40,
        choices=TicketStatus.choices,
        default=TicketStatus.PENDING_FACILITY_MANAGER_REVIEW,
    )
    assessment_outcome = models.CharField(
        max_length=30, choices=AssessmentOutcome.choices, blank=True
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_tickets"
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="closed_tickets",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            # Default listing: Open/Closed tab (status IN ...) sorted by created time.
            models.Index(fields=["status", "-created_at"], name="ticket_status_created_idx"),
            # Department POC's queue: tickets currently routed to their department by status.
            models.Index(fields=["department", "status"], name="ticket_dept_status_idx"),
            # Technician's queue.
            models.Index(fields=["technician", "status"], name="ticket_tech_status_idx"),
            # Facility Manager's view of their location.
            models.Index(fields=["facility_manager", "status"], name="ticket_fm_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=TicketStatus.values), name="ticket_status_valid"
            ),
            models.CheckConstraint(
                condition=~Q(status=TicketStatus.PENDING_TECHNICIAN_ASSESSMENT)
                | Q(technician__isnull=False),
                name="ticket_assessment_requires_technician",
            ),
            models.CheckConstraint(
                condition=(Q(status__in=sorted(CLOSED_STATUSES)) & Q(closed_at__isnull=False))
                | (~Q(status__in=sorted(CLOSED_STATUSES)) & Q(closed_at__isnull=True)),
                name="ticket_closed_at_matches_status",
            ),
        ]

    @property
    def number(self) -> str:
        return f"TKT-{self.pk + TICKET_NUMBER_OFFSET}"

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    def __str__(self):
        return f"#{self.number} {self.title}"


class ActivityKind(models.TextChoices):
    CREATED = "created", "created the ticket"
    AUTO_ASSIGNED = "auto_assigned", "auto-assigned the ticket"
    FORWARDED_TO_DEPARTMENT = "forwarded_to_department", "forwarded to department"
    ASSIGNED_TECHNICIAN = "assigned_technician", "assigned technician"
    CHANGED_DEPARTMENT = "changed_department", "changed department"
    CHANGED_STATUS = "changed_status", "changed status of the ticket"
    PENDING_CLIENT_CONFIRMATION = (
        "pending_client_confirmation",
        "marked the ticket resolved, pending client confirmation",
    )
    RESOLVED = "resolved", "marked the ticket resolved"
    CLOSED = "closed", "closed the ticket"
    COMMENTED = "commented", "commented"
    EDITED_DESCRIPTION = "edited_description", "edited the description"


class TicketComment(models.Model):
    """
    User-written content on a ticket: free comments, plus the notes attached to
    actions (forwarding note, assessment comment, closing note). Stored as
    sanitised rich-text HTML; `body_text` is the plain-text projection used for
    previews, search and notifications.
    """

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ticket_comments"
    )
    body_html = models.TextField(blank=True)
    body_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["ticket", "created_at"], name="comment_ticket_created_idx"),
        ]

    def __str__(self):
        return f"{self.ticket_id}:{self.body_text[:40]}"


class AttachmentStatus(models.TextChoices):
    PENDING = "pending", "Pending upload"  # presigned URL issued, not yet linked
    ATTACHED = "attached", "Attached"  # verified in storage and linked to a comment


class Attachment(models.Model):
    """
    A file in object storage (S3 / MinIO). The browser uploads directly to the
    bucket with a presigned POST; the row starts PENDING and only becomes
    ATTACHED once the server has verified the object exists and linked it to a
    comment. Stale PENDING rows are removed by a periodic Celery task.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="attachments")
    comment = models.ForeignKey(
        TicketComment,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="attachments",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="attachments"
    )
    storage_key = models.CharField(max_length=500, unique=True)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size = models.PositiveBigIntegerField()
    status = models.CharField(
        max_length=20, choices=AttachmentStatus.choices, default=AttachmentStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            # Orphan cleanup: pending uploads older than N hours.
            models.Index(fields=["status", "created_at"], name="attachment_status_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=AttachmentStatus.values), name="attachment_status_valid"
            ),
            models.CheckConstraint(condition=Q(size__gt=0), name="attachment_size_positive"),
            models.CheckConstraint(
                condition=~Q(status=AttachmentStatus.ATTACHED) | Q(comment__isnull=False),
                name="attachment_attached_has_comment",
            ),
        ]

    def __str__(self):
        return self.original_name

    @property
    def kind(self) -> str:
        if self.content_type.startswith("image/"):
            return "image"
        if self.content_type.startswith("video/"):
            return "video"
        return "file"


class TicketActivity(models.Model):
    """
    Append-only audit trail. `actor=None` means the System. Comments and action
    notes live in TicketComment and are referenced from their activity, so the
    timeline is still one ordered query.
    """

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="activities")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ticket_activities",
    )
    kind = models.CharField(max_length=30, choices=ActivityKind.choices)
    from_value = models.CharField(max_length=200, blank=True)
    to_value = models.CharField(max_length=200, blank=True)
    comment = models.OneToOneField(
        TicketComment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="activity",
    )
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["ticket", "created_at"], name="activity_ticket_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=ActivityKind.values), name="activity_kind_valid"
            ),
            models.CheckConstraint(
                condition=~Q(kind=ActivityKind.COMMENTED) | Q(comment__isnull=False),
                name="activity_commented_has_comment",
            ),
        ]

    def __str__(self):
        return f"{self.ticket_id}:{self.kind}"

    @property
    def is_comment(self) -> bool:
        return self.kind == ActivityKind.COMMENTED
