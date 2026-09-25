import logging

from django.conf import settings
from django.db.models import Count, Prefetch, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.accounts.models import Role, User
from apps.accounts.permissions import CanCreateTicket
from apps.accounts.serializers import UserSummarySerializer

from . import services
from .filters import StableOrderingFilter, TicketFilter
from .models import CLOSED_STATUSES, OPEN_STATUSES, Ticket, TicketActivity
from . import policies
from .policies import visible_tickets
from .serializers import (
    AssignWorkerSerializer,
    AttachmentUploadSerializer,
    ChangeDepartmentSerializer,
    CloseSerializer,
    CommentCreateSerializer,
    EditDescriptionSerializer,
    ForwardToDepartmentSerializer,
    SubmitAssessmentSerializer,
    TicketCreateSerializer,
    TicketDetailSerializer,
    TicketListSerializer,
)

logger = logging.getLogger(__name__)


class TicketViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    GET    /api/tickets/                     paginated list (?tab, ?search, filters, ?ordering)
    POST   /api/tickets/                     create (title + issue tags; first tag routes)
    GET    /api/tickets/counts/              open/closed totals for the current filters
    GET    /api/tickets/{id}/                detail incl. activity + available actions
    GET    /api/tickets/{id}/assignable-users/  ?search= — people the POC can assign
    POST   /api/tickets/{id}/forward-to-department/  FM routes the ticket to a department
    POST   /api/tickets/{id}/assign-worker/
    POST   /api/tickets/{id}/change-department/
    POST   /api/tickets/{id}/submit-assessment/
    POST   /api/tickets/{id}/close/
    POST   /api/tickets/{id}/mark-resolved/
    POST   /api/tickets/{id}/description/        edit the issue description (rich text)
    POST   /api/tickets/{id}/comments/           rich text + attachment ids
    POST   /api/tickets/{id}/attachments/        presigned upload for a new file
    """

    filter_backends = [DjangoFilterBackend, StableOrderingFilter]
    filterset_class = TicketFilter
    ordering_fields = ["created_at"]
    ordering = ["-created_at", "-id"]

    def get_queryset(self):
        # Every relation the serializers touch is loaded up front: a page of
        # tickets costs a fixed number of queries regardless of page size.
        qs = Ticket.objects.select_related(
            "client_office__client",
            "client_office__property__location",
            "facility_manager__department",
            "department",
            "department_poc__department",
            "technician__department",
            "created_by__department",
        ).prefetch_related("floors", "client_office__floors", "issue_types")
        if self.action not in ("list", "counts"):
            qs = qs.prefetch_related(
                Prefetch(
                    "activities",
                    queryset=TicketActivity.objects.select_related(
                        "actor__department", "comment"
                    ).prefetch_related("comment__attachments"),
                )
            )
        return visible_tickets(self.request.user, qs)

    def filter_queryset(self, queryset):
        # List filters (?search=, ?status=...) must not affect detail routes, e.g.
        # ?search= on assignable-users searches users, not tickets.
        return super().filter_queryset(queryset) if self.action == "list" else queryset

    def get_serializer_class(self):
        return TicketListSerializer if self.action == "list" else TicketDetailSerializer

    def get_permissions(self):
        if self.action == "create":
            return [*super().get_permissions(), CanCreateTicket()]
        return super().get_permissions()

    # --- create ------------------------------------------------------------

    def create(self, request):
        serializer = TicketCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        ticket = services.create_ticket(user=request.user, **serializer.validated_data)
        data = TicketDetailSerializer(
            self.get_queryset().get(pk=ticket.pk), context={"request": request}
        ).data
        return Response(data, status=status.HTTP_201_CREATED)

    # --- counts ------------------------------------------------------------

    @action(detail=False, methods=["get"])
    def counts(self, request):
        params = request.query_params.copy()
        params.pop("tab", None)
        qs = TicketFilter(params, queryset=self.get_queryset(), request=request).qs
        # One query with conditional aggregation instead of two COUNTs.
        totals = qs.order_by().aggregate(
            open=Count("id", filter=Q(status__in=list(OPEN_STATUSES))),
            closed=Count("id", filter=Q(status__in=list(CLOSED_STATUSES))),
        )
        return Response(totals)

    # --- workflow actions ----------------------------------------------------

    def _detail_response(self, ticket_id):
        ticket = self.get_queryset().get(pk=ticket_id)
        return Response(self.get_serializer(ticket).data)

    def _run(self, input_serializer_cls, service, **extra):
        ticket = self.get_object()  # 404 if the user cannot see the ticket
        data = {}
        if input_serializer_cls:
            serializer = input_serializer_cls(data=self.request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
        service(user=self.request.user, ticket_id=ticket.pk, **extra, **data)
        return self._detail_response(ticket.pk)

    @action(detail=True, methods=["get"], url_path="assignable-users")
    def assignable_users(self, request, pk=None):
        """Jira-style assignee picker: active technicians of the ticket's department."""
        ticket = self.get_object()
        if not policies.has_permission(request.user, ticket, "assign_worker"):
            raise PermissionDenied("You cannot assign a worker on this ticket.")
        users = User.objects.select_related("department").filter(
            role=Role.TECHNICIAN, department_id=ticket.department_id, is_active=True
        )
        term = request.query_params.get("search", "").strip()
        if term:
            users = users.filter(
                Q(first_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(username__icontains=term)
            )
        users = users.order_by("first_name", "last_name")[:20]
        return Response(
            {
                "results": UserSummarySerializer(users, many=True).data,
                "current_id": ticket.technician_id,
            }
        )

    @action(detail=True, methods=["post"], url_path="forward-to-department")
    def forward_to_department(self, request, pk=None):
        ticket = self.get_object()
        serializer = ForwardToDepartmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.forward_to_department(
            user=request.user,
            ticket_id=ticket.pk,
            department=serializer.validated_data["department_id"],
            note=serializer.validated_data["note"],
        )
        return self._detail_response(ticket.pk)

    @action(detail=True, methods=["post"], url_path="assign-worker")
    def assign_worker(self, request, pk=None):
        ticket = self.get_object()
        serializer = AssignWorkerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.assign_worker(
            user=request.user,
            ticket_id=ticket.pk,
            technician=serializer.validated_data["technician_id"],
        )
        return self._detail_response(ticket.pk)

    @action(detail=True, methods=["post"], url_path="change-department")
    def change_department(self, request, pk=None):
        ticket = self.get_object()
        serializer = ChangeDepartmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.change_department(
            user=request.user,
            ticket_id=ticket.pk,
            department=serializer.validated_data["department_id"],
            note=serializer.validated_data["note"],
        )
        # The POC may lose visibility once the ticket leaves their department.
        if not self.get_queryset().filter(pk=ticket.pk).exists():
            return Response({"id": ticket.pk, "visible": False})
        return self._detail_response(ticket.pk)

    @action(detail=True, methods=["post"], url_path="submit-assessment")
    def submit_assessment(self, request, pk=None):
        ticket = self.get_object()
        serializer = SubmitAssessmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.submit_assessment(
            user=request.user, ticket_id=ticket.pk, **serializer.validated_data
        )
        # Fully resolved clears the technician (back to Unassigned), so the technician
        # who just submitted may no longer see it — their queue is scoped to assignment.
        if not self.get_queryset().filter(pk=ticket.pk).exists():
            return Response({"id": ticket.pk, "visible": False})
        return self._detail_response(ticket.pk)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        return self._run(CloseSerializer, services.close_ticket)

    @action(detail=True, methods=["post"], url_path="mark-resolved")
    def mark_resolved(self, request, pk=None):
        return self._run(None, services.mark_resolved)

    @action(detail=True, methods=["post"])
    def description(self, request, pk=None):
        return self._run(EditDescriptionSerializer, services.edit_description)

    @action(detail=True, methods=["post"])
    def comments(self, request, pk=None):
        ticket = self.get_object()
        serializer = CommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.add_comment(
            user=request.user,
            ticket_id=ticket.pk,
            body_html=serializer.validated_data["body"],
            attachment_ids=serializer.validated_data["attachment_ids"],
        )
        response = self._detail_response(ticket.pk)
        response.status_code = status.HTTP_201_CREATED
        return response

    @action(detail=True, methods=["post"])
    def attachments(self, request, pk=None):
        """Step 1 of an upload: returns a presigned POST the browser sends the file to."""
        ticket = self.get_object()
        serializer = AttachmentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attachment, upload = services.request_attachment_upload(
            user=request.user, ticket_id=ticket.pk, **serializer.validated_data
        )
        return Response(
            {"id": attachment.pk, "upload": upload, "max_bytes": settings.ATTACHMENT_MAX_BYTES},
            status=status.HTTP_201_CREATED,
        )
