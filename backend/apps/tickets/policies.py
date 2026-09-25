"""
Authorization rules for tickets, kept in one place so the API, serializers and
tests all agree.

Routing: a new ticket goes to the Facility Manager of its location first. The FM
forwards it to a department (assigning that department's POC); only then can the
Department POC assign a technician. The FM never assigns a worker directly, and
the POC never picks the FM's part of the routing — each step is one handoff.

Visibility (who can see a ticket at all — others get 404):
  - Client POC        : tickets raised for any office of their client company
  - Facility Manager  : tickets auto-linked to them (their location), or that they raised
  - Department POC    : tickets forwarded to their department, or that they raised
  - Technician        : tickets currently assigned to them
  - Admin             : everything

Actions (visible but not permitted -> 403, permitted but wrong state -> 409):
  - forward_to_department : the Facility Manager the ticket is linked to
  - mark_resolved     : a Client POC of the ticket's client (and only them)
  - assign_worker /
    change_department  : the POC of the ticket's current department; while the
                          ticket is Pending Blockage Resolution, the ticket's
                          Facility Manager may also reassign it (either can act)
  - close             : the POC of the ticket's current department
  - submit_assessment : the currently assigned technician
  - comment           : anyone who can see the ticket, while it is open
"""

from django.db.models import Q, QuerySet

from apps.accounts.models import Role, User

from .models import OPEN_STATUSES, Ticket, TicketStatus

S = TicketStatus

# action -> statuses it can be performed from. Anything else is an invalid transition (409).
ALLOWED_FROM: dict[str, frozenset[str]] = {
    "forward_to_department": frozenset({S.PENDING_FACILITY_MANAGER_REVIEW}),
    # Includes reassigning a different technician while the assessment is pending.
    "assign_worker": frozenset(
        {
            S.PENDING_TECHNICIAN_ASSIGNMENT,
            S.PENDING_TECHNICIAN_ASSESSMENT,
            S.PENDING_POC_REVIEW,
            S.PENDING_BLOCKAGE_RESOLUTION,
        }
    ),
    "change_department": frozenset(
        {S.PENDING_TECHNICIAN_ASSIGNMENT, S.PENDING_POC_REVIEW, S.PENDING_BLOCKAGE_RESOLUTION}
    ),
    "submit_assessment": frozenset({S.PENDING_TECHNICIAN_ASSESSMENT}),
    "close": frozenset({S.PENDING_POC_REVIEW, S.PENDING_BLOCKAGE_RESOLUTION}),
    "mark_resolved": OPEN_STATUSES,
    "comment": OPEN_STATUSES,
    "edit_description": OPEN_STATUSES,
}

# Workflow actions that put the ticket in the user's "Action Required" queue.
WORKFLOW_ACTIONS = (
    "forward_to_department",
    "assign_worker",
    "change_department",
    "submit_assessment",
    "close",
)


def visible_tickets(user: User, qs: QuerySet[Ticket] | None = None) -> QuerySet[Ticket]:
    qs = Ticket.objects.all() if qs is None else qs
    match user.role:
        case Role.ADMIN:
            return qs
        case Role.CLIENT_POC:
            return qs.filter(client_office__client_id=user.client_office.client_id)
        case Role.FACILITY_MANAGER:
            return qs.filter(Q(facility_manager=user) | Q(created_by=user))
        case Role.DEPARTMENT_POC:
            # Not yet forwarded by the FM -> not in the department's queue, unless self-raised.
            return qs.filter(
                Q(department_id=user.department_id, department_poc__isnull=False)
                | Q(created_by=user)
            )
        case Role.TECHNICIAN:
            return qs.filter(technician=user)
    return qs.none()


def is_department_poc(user: User, ticket: Ticket) -> bool:
    if user.role == Role.ADMIN:
        return True
    return user.role == Role.DEPARTMENT_POC and user.department_id == ticket.department_id


def is_ticket_facility_manager(user: User, ticket: Ticket) -> bool:
    if user.role == Role.ADMIN:
        return True
    return user.role == Role.FACILITY_MANAGER and ticket.facility_manager_id == user.id


def can_mark_resolved(user: User, ticket: Ticket) -> bool:
    # Client POC only — deliberately no Admin or creator bypass. This is the client's
    # personal call ("is it fixed for me?"), not an operational action: an internal
    # user who raised it on the client's behalf (e.g. an FM) doesn't get to decide
    # this for them, and showing it to Admin alongside the POC's CTA panel would be
    # confusing, not useful oversight.
    return (
        user.role == Role.CLIENT_POC
        and user.client_office.client_id == ticket.client_office.client_id
    )


def can_reassign_blockage(user: User, ticket: Ticket) -> bool:
    """While a ticket is blocked, the Facility Manager can also step in and reassign it."""
    return ticket.status == S.PENDING_BLOCKAGE_RESOLUTION and is_ticket_facility_manager(
        user, ticket
    )


def has_permission(user: User, ticket: Ticket, action: str) -> bool:
    """Role/relationship check (the blockage exception below is the one case that also
    looks at status, since it only applies to the Facility Manager while blocked)."""
    match action:
        case "forward_to_department":
            return is_ticket_facility_manager(user, ticket)
        case "assign_worker" | "change_department":
            return is_department_poc(user, ticket) or can_reassign_blockage(user, ticket)
        case "close":
            return is_department_poc(user, ticket)
        case "submit_assessment":
            return ticket.technician_id == user.id
        case "mark_resolved":
            return can_mark_resolved(user, ticket)
        case "comment" | "edit_description":
            return True  # visibility is already enforced by the queryset
    return False


def is_allowed_from(ticket: Ticket, action: str) -> bool:
    return ticket.status in ALLOWED_FROM[action]


def available_actions(user: User, ticket: Ticket) -> list[str]:
    return [
        action
        for action in ALLOWED_FROM
        if has_permission(user, ticket, action) and is_allowed_from(ticket, action)
    ]


def action_required(user: User, ticket: Ticket) -> bool:
    """Admins can do everything, so only flag tickets actually routed to the user."""
    if user.role == Role.ADMIN:
        return False
    waiting_on_technician = ticket.status == S.PENDING_TECHNICIAN_ASSESSMENT
    return any(
        has_permission(user, ticket, a)
        and is_allowed_from(ticket, a)
        # Reassigning is possible then, but the POC isn't the one blocking the ticket.
        and not (a == "assign_worker" and waiting_on_technician)
        for a in WORKFLOW_ACTIONS
    )
