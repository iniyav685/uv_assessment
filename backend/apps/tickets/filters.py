import re

import django_filters
from django.db.models import Q
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter

from .models import CLOSED_STATUSES, OPEN_STATUSES, TICKET_NUMBER_OFFSET, Ticket, TicketStatus

TICKET_NUMBER_RE = re.compile(r"^#?(?:tkt-?)?(\d+)$", re.IGNORECASE)


class NumberInFilter(django_filters.BaseInFilter, django_filters.NumberFilter):
    """Comma-separated ids: ?client=1,2"""


class CharInFilter(django_filters.BaseInFilter, django_filters.CharFilter):
    pass


class TicketFilter(django_filters.FilterSet):
    tab = django_filters.ChoiceFilter(
        choices=[("open", "Open"), ("closed", "Closed")], method="filter_tab"
    )
    status = CharInFilter(method="filter_status")
    client = NumberInFilter(field_name="client_office__client_id", lookup_expr="in")
    department = NumberInFilter(field_name="department_id", lookup_expr="in")
    facility_manager = NumberInFilter(field_name="facility_manager_id", lookup_expr="in")
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = Ticket
        fields = ["tab", "status", "client", "department", "facility_manager", "search"]

    def filter_tab(self, qs, name, value):
        statuses = OPEN_STATUSES if value == "open" else CLOSED_STATUSES
        return qs.filter(status__in=list(statuses))

    def filter_search(self, qs, name, value):
        term = value.strip()
        if not term:
            return qs
        q = (
            Q(title__icontains=term)
            | Q(description__icontains=term)
            | Q(primary_issue_type__name__icontains=term)
            | Q(client_office__client__name__icontains=term)
            | Q(client_office__property__code__icontains=term)
        )
        if match := TICKET_NUMBER_RE.match(term):
            q |= Q(pk=int(match.group(1)) - TICKET_NUMBER_OFFSET)
        return qs.filter(q)

    def filter_status(self, qs, name, value):
        # Reject unknown values with a 400 instead of silently returning nothing.
        unknown = set(value) - set(TicketStatus.values)
        if unknown:
            raise ValidationError({"status": [f"Unknown status: {', '.join(sorted(unknown))}"]})
        return qs.filter(status__in=value)


class StableOrderingFilter(OrderingFilter):
    """Adds an id tie-breaker so pagination is deterministic for equal timestamps."""

    def get_ordering(self, request, queryset, view):
        ordering = super().get_ordering(request, queryset, view)
        if not ordering:
            return ordering
        tiebreak = "id" if ordering[0].lstrip("-") == ordering[0] else "-id"
        return [*ordering, tiebreak]
