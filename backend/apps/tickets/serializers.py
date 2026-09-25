from rest_framework import serializers

from apps.accounts.models import Role, User
from apps.accounts.serializers import UserSummarySerializer
from apps.common import storage
from apps.common.richtext import html_to_text, sanitize_html
from apps.organizations.models import ClientOffice, Department, Floor, IssueType

from . import policies
from .models import AssessmentOutcome, Attachment, Ticket, TicketActivity, TicketComment

MAX_ISSUES_PER_REQUEST = 5  # issue tags per ticket
MAX_TEXT = 2000
MAX_RICH_TEXT = 20_000  # HTML from a rich-text editor; markup adds overhead over plain text


class NamedRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class AttachmentSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="original_name")
    url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = ("id", "name", "content_type", "size", "kind", "url")
        read_only_fields = fields

    def get_url(self, obj):
        # Short-lived presigned GET: the bucket itself stays private.
        return storage.presign_download(
            obj.storage_key, obj.original_name, inline=obj.kind in ("image", "video")
        )


class CommentSerializer(serializers.ModelSerializer):
    attachments = AttachmentSerializer(many=True)

    class Meta:
        model = TicketComment
        fields = ("id", "body_html", "body_text", "attachments")
        read_only_fields = fields


class ActivitySerializer(serializers.ModelSerializer):
    actor = UserSummarySerializer(allow_null=True)
    kind_label = serializers.CharField(source="get_kind_display")
    comment = CommentSerializer(allow_null=True)

    class Meta:
        model = TicketActivity
        fields = (
            "id",
            "kind",
            "kind_label",
            "actor",
            "from_value",
            "to_value",
            "comment",
            "meta",
            "is_comment",
            "created_at",
        )
        read_only_fields = fields


def format_location(ticket: Ticket) -> str:
    """e.g. 'Harness-1317; 2F, 3F', or 'HSR-1317; All Floors' when every floor of a larger
    office is affected (listing two floors is clearer than 'All Floors')."""
    office = ticket.client_office
    selected = list(ticket.floors.all())  # prefetched
    total = len(office.floors.all())  # prefetched
    if not selected:
        return office.label
    if total > 2 and len(selected) == total:
        return f"{office.label}; All Floors"
    return f"{office.label}; {', '.join(f.label for f in selected)}"


class TicketListSerializer(serializers.ModelSerializer):
    number = serializers.CharField(read_only=True)
    status_label = serializers.CharField(source="get_status_display")
    location = serializers.SerializerMethodField()
    area = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    client = NamedRefSerializer(source="client_office.client")
    department = NamedRefSerializer()
    facility_manager = UserSummarySerializer(allow_null=True)
    created_by = UserSummarySerializer()
    assignees = serializers.SerializerMethodField()
    action_required = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = (
            "id",
            "number",
            "title",
            "status",
            "status_label",
            "location",
            "area",
            "tags",
            "client",
            "department",
            "facility_manager",
            "created_by",
            "created_at",
            "assignees",
            "action_required",
        )
        read_only_fields = fields

    def get_location(self, obj):
        return format_location(obj)

    def get_tags(self, obj):
        """Issue tags, primary first (prefetched: no extra queries)."""
        tags = sorted(
            obj.issue_types.all(), key=lambda t: (t.id != obj.primary_issue_type_id, t.name)
        )
        return [
            {"id": t.id, "name": t.name, "primary": t.id == obj.primary_issue_type_id} for t in tags
        ]

    def get_area(self, obj):
        location = obj.client_office.property.location
        return {"id": location.id, "name": str(location)}

    def get_assignees(self, obj):
        # Before the FM forwards it, they're the one with the ball; after, the POC/technician are.
        people = [obj.department_poc, obj.technician] if obj.department_poc else [obj.facility_manager]
        return UserSummarySerializer([u for u in people if u], many=True).data

    def get_action_required(self, obj):
        return policies.action_required(self.context["request"].user, obj)


class TicketDetailSerializer(TicketListSerializer):
    office = serializers.SerializerMethodField()
    floors = serializers.SerializerMethodField()
    department_poc = UserSummarySerializer(allow_null=True)
    technician = UserSummarySerializer(allow_null=True)
    assessment_outcome_label = serializers.SerializerMethodField()
    available_actions = serializers.SerializerMethodField()
    activities = ActivitySerializer(many=True)

    class Meta(TicketListSerializer.Meta):
        fields = (
            *TicketListSerializer.Meta.fields,
            "description",
            "office",
            "floors",
            "department_poc",
            "technician",
            "assessment_outcome",
            "assessment_outcome_label",
            "closed_at",
            "available_actions",
            "activities",
        )
        read_only_fields = fields

    def get_office(self, obj):
        return {"id": obj.client_office_id, "label": obj.client_office.label}

    def get_floors(self, obj):
        return [{"id": f.id, "label": f.label} for f in obj.floors.all()]

    def get_assessment_outcome_label(self, obj):
        return AssessmentOutcome(obj.assessment_outcome).label if obj.assessment_outcome else ""

    def get_available_actions(self, obj):
        return policies.available_actions(self.context["request"].user, obj)


def creatable_offices(user: User):
    """Offices a user may raise tickets for."""
    qs = ClientOffice.objects.select_related("client", "property").prefetch_related("floors")
    match user.role:
        case Role.CLIENT_POC:
            return qs.filter(pk=user.client_office_id)
        case Role.FACILITY_MANAGER:
            return qs.filter(property__location_id=user.location_id)
        case Role.DEPARTMENT_POC | Role.ADMIN:
            return qs
    return qs.none()


class TicketCreateSerializer(serializers.Serializer):
    client_office_id = serializers.IntegerField(required=False)
    title = serializers.CharField(min_length=3, max_length=150, trim_whitespace=True)
    # Issue tags; the first one is the primary issue that decides routing.
    issue_type_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
        max_length=MAX_ISSUES_PER_REQUEST,
        error_messages={"empty": "Add at least one issue tag."},
    )
    floor_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )
    # Rich-text HTML from the editor; sanitised below.
    description = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=MAX_RICH_TEXT
    )

    def validate(self, attrs):
        user: User = self.context["request"].user
        errors: dict[str, list[str]] = {}

        # Client office — Client POCs are pinned to their own office.
        office_id = attrs.get("client_office_id")
        if user.role == Role.CLIENT_POC:
            office_id = user.client_office_id
        office = creatable_offices(user).filter(pk=office_id).first() if office_id else None
        if office is None:
            errors["client_office_id"] = ["Select a client you are allowed to raise tickets for."]

        # Issue tags — order is preserved; the first tag is the primary issue.
        issue_ids = list(dict.fromkeys(attrs["issue_type_ids"]))
        issues = list(IssueType.objects.select_related("department").filter(pk__in=issue_ids))
        if len(issues) != len(issue_ids):
            errors["issue_type_ids"] = ["One or more selected issues do not exist."]
        issues.sort(key=lambda i: issue_ids.index(i.id))

        # Description — optional for clients, required for internal users (per wireframe).
        description_html = sanitize_html(attrs["description"])
        if user.is_internal and not html_to_text(description_html):
            errors["description"] = ["Describe the issue."]

        # Floors — required only when the office has more than one floor.
        floors: list[Floor] = []
        if office is not None:
            office_floors = {f.id: f for f in office.floors.all()}
            floor_ids = list(dict.fromkeys(attrs["floor_ids"]))
            if len(office_floors) > 1:
                if not floor_ids:
                    errors["floor_ids"] = ["Select at least one floor."]
                elif any(fid not in office_floors for fid in floor_ids):
                    errors["floor_ids"] = ["Selected floors must belong to this office."]
                else:
                    floors = [office_floors[fid] for fid in floor_ids]
            else:
                floors = list(office_floors.values())

        if errors:
            raise serializers.ValidationError(errors)

        return {
            "client_office": office,
            "title": attrs["title"],
            "issue_types": issues,
            "floors": floors,
            "description": description_html,
        }


class ForwardToDepartmentSerializer(serializers.Serializer):
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        error_messages={"does_not_exist": "Select a valid department."},
    )
    note = serializers.CharField(
        max_length=MAX_TEXT, required=False, allow_blank=True, default="", trim_whitespace=True
    )


class AssignWorkerSerializer(serializers.Serializer):
    technician_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=Role.TECHNICIAN),
        error_messages={"does_not_exist": "Select a valid technician."},
    )


class ChangeDepartmentSerializer(serializers.Serializer):
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        error_messages={"does_not_exist": "Select a valid department."},
    )
    note = serializers.CharField(max_length=MAX_TEXT, trim_whitespace=True)


class SubmitAssessmentSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=AssessmentOutcome.choices)
    comment = serializers.CharField(
        max_length=MAX_TEXT, required=False, allow_blank=True, default="", trim_whitespace=True
    )


class CloseSerializer(serializers.Serializer):
    note = serializers.CharField(
        max_length=MAX_TEXT, required=False, allow_blank=True, default="", trim_whitespace=True
    )


class CommentCreateSerializer(serializers.Serializer):
    # Rich-text HTML from the editor; sanitised in the service layer.
    body = serializers.CharField(max_length=MAX_RICH_TEXT, allow_blank=True, required=False, default="")
    attachment_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list, max_length=20
    )


class EditDescriptionSerializer(serializers.Serializer):
    # Rich-text HTML from the editor; sanitised in the service layer.
    description = serializers.CharField(max_length=MAX_RICH_TEXT, allow_blank=True)


class AttachmentUploadSerializer(serializers.Serializer):
    filename = serializers.CharField(max_length=255)
    content_type = serializers.CharField(max_length=100)
    size = serializers.IntegerField(min_value=1)
