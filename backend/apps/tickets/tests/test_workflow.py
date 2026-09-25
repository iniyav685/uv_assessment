"""Business rules: creation, routing and state transitions."""

import pytest
from django.db import IntegrityError
from django.urls import reverse

from apps.accounts.models import Role
from apps.organizations.models import Client, ClientOffice, Floor, Property
from apps.tickets.models import ActivityKind, Ticket, TicketStatus
from conftest import make_user

from .helpers import act, create_ticket, raise_ac_ticket

pytestmark = pytest.mark.django_db


def test_ticket_has_free_text_title_and_issue_tags_routed_by_first_tag(auth_client, world):
    res = create_ticket(
        auth_client(world.client),
        title="  AC and network both down on 2F  ",
        issue_type_ids=[world.internet.id, world.ac.id],
        floor_ids=[world.floors[0].id],
    )

    assert res.status_code == 201
    ticket = res.json()
    assert ticket["title"] == "AC and network both down on 2F"
    # First tag is primary and decides routing.
    assert ticket["tags"] == [
        {"id": world.internet.id, "name": "Internet not working", "primary": True},
        {"id": world.ac.id, "name": "AC not cooling", "primary": False},
    ]
    # Suggested department from the primary tag; routing itself waits on the FM.
    assert ticket["department"]["name"] == "IT"
    assert ticket["assignees"][0]["id"] == world.fm.id
    assert ticket["status"] == TicketStatus.PENDING_FACILITY_MANAGER_REVIEW
    assert ticket["location"] == "Harness-1317; 2F"
    assert [a["kind"] for a in ticket["activities"]] == ["created", "auto_assigned"]
    assert ticket["activities"][1]["actor"] is None  # "System"
    assert Ticket.objects.count() == 1


def test_creation_validates_title_floors_and_internal_rules(auth_client, world):
    # Title required.
    res = create_ticket(auth_client(world.client), issue_type_ids=[world.ac.id])
    assert res.status_code == 400
    assert "title" in res.json()["error"]["details"]

    # Multi-floor office needs a floor.
    res = create_ticket(auth_client(world.client), title="AC down", issue_type_ids=[world.ac.id])
    assert "floor_ids" in res.json()["error"]["details"]

    # No tags -> rejected.
    res = create_ticket(auth_client(world.client), title="Hot", issue_type_ids=[])
    assert "issue_type_ids" in res.json()["error"]["details"]

    # Internal users must describe the issue.
    res = create_ticket(
        auth_client(world.fm),
        client_office_id=world.acme.id,
        title="AC down",
        issue_type_ids=[world.ac.id],
        floor_ids=[world.floors[0].id],
    )
    assert res.status_code == 400
    assert "description" in res.json()["error"]["details"]

    # Technicians cannot raise tickets at all.
    res = create_ticket(auth_client(world.tech), title="x" * 5, issue_type_ids=[world.ac.id])
    assert res.status_code == 403


def test_full_lifecycle_through_poc_review(auth_client, world):
    ticket_id = raise_ac_ticket(auth_client, world)
    poc, tech = auth_client(world.tech_poc), auth_client(world.tech)

    res = act(poc, ticket_id, "assign-worker", technician_id=world.tech.id)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == TicketStatus.PENDING_TECHNICIAN_ASSESSMENT
    assert [a["id"] for a in body["assignees"]] == [world.tech_poc.id, world.tech.id]

    # The technician now sees it, with the assessment CTA.
    detail = tech.get(reverse("ticket-detail", args=[ticket_id])).json()
    assert detail["available_actions"] == ["submit_assessment", "comment", "edit_description"]
    assert detail["action_required"] is True

    res = act(tech, ticket_id, "submit-assessment", outcome="fully_resolved")
    assert res.json() == {"id": ticket_id, "visible": False}  # unassigned; left the tech's queue
    ticket = Ticket.objects.get(pk=ticket_id)
    assert ticket.status == TicketStatus.PENDING_POC_REVIEW
    assert ticket.technician is None
    assert tech.get(reverse("ticket-detail", args=[ticket_id])).status_code == 404

    res = act(poc, ticket_id, "close", note="Verified.")
    assert res.json()["status"] == TicketStatus.PENDING_CLIENT_CONFIRMATION
    # The POC's review doesn't fully close it — no closed_at until the client confirms.
    assert Ticket.objects.get(pk=ticket_id).closed_at is None

    # The Department POC can no longer act on it; only the Client POC's confirmation can.
    assert act(poc, ticket_id, "close").status_code == 409

    res = act(auth_client(world.client), ticket_id, "mark-resolved")
    assert res.json()["status"] == TicketStatus.RESOLVED

    kinds = list(Ticket.objects.get(pk=ticket_id).activities.values_list("kind", flat=True))
    assert kinds == [
        ActivityKind.CREATED,
        ActivityKind.AUTO_ASSIGNED,
        ActivityKind.FORWARDED_TO_DEPARTMENT,
        ActivityKind.ASSIGNED_TECHNICIAN,
        ActivityKind.CHANGED_STATUS,
        ActivityKind.PENDING_CLIENT_CONFIRMATION,
        ActivityKind.RESOLVED,
    ]


def test_facility_manager_forwards_before_poc_can_act(auth_client, world):
    ticket_id = raise_ac_ticket(auth_client, world, forward=False)
    poc = auth_client(world.tech_poc)

    # Not yet forwarded: no department POC, and the POC can't see or act on it.
    ticket = Ticket.objects.get(pk=ticket_id)
    assert ticket.status == TicketStatus.PENDING_FACILITY_MANAGER_REVIEW
    assert ticket.department_poc is None
    assert poc.get(reverse("ticket-detail", args=[ticket_id])).status_code == 404
    res = act(poc, ticket_id, "assign-worker", technician_id=world.tech.id)
    assert res.status_code == 404

    # Only the ticket's own FM can forward it — a different location's FM can't even see it.
    res = act(
        auth_client(world.other_fm),
        ticket_id,
        "forward-to-department",
        department_id=world.technical.id,
    )
    assert res.status_code == 404

    res = act(
        auth_client(world.fm), ticket_id, "forward-to-department", department_id=world.technical.id
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == TicketStatus.PENDING_TECHNICIAN_ASSIGNMENT
    assert body["department_poc"]["id"] == world.tech_poc.id
    assert [a["kind"] for a in body["activities"]] == [
        "created",
        "auto_assigned",
        "forwarded_to_department",
    ]

    # Now the POC can see it and take over.
    assert poc.get(reverse("ticket-detail", args=[ticket_id])).status_code == 200
    res = act(poc, ticket_id, "assign-worker", technician_id=world.tech.id)
    assert res.status_code == 200

    # The FM's one action is forwarding — not assigning a worker directly.
    res = act(
        auth_client(world.fm),
        raise_ac_ticket(auth_client, world, forward=False),
        "assign-worker",
        technician_id=world.tech.id,
    )
    assert res.status_code == 403


def test_partial_resolution_requires_comment_and_blocks_ticket(auth_client, world):
    ticket_id = raise_ac_ticket(auth_client, world)
    act(auth_client(world.tech_poc), ticket_id, "assign-worker", technician_id=world.tech.id)
    tech = auth_client(world.tech)

    res = act(tech, ticket_id, "submit-assessment", outcome="partially_resolved")
    assert res.status_code == 400
    assert "comment" in res.json()["error"]["details"]

    res = act(tech, ticket_id, "submit-assessment", outcome="partially_resolved", comment="Gas")
    assert res.json()["status"] == TicketStatus.PENDING_BLOCKAGE_RESOLUTION


def _block_ticket(auth_client, world) -> int:
    ticket_id = raise_ac_ticket(auth_client, world)
    act(auth_client(world.tech_poc), ticket_id, "assign-worker", technician_id=world.tech.id)
    act(
        auth_client(world.tech),
        ticket_id,
        "submit-assessment",
        outcome="needs_reassignment",
        comment="Not our department",
    )
    assert Ticket.objects.get(pk=ticket_id).status == TicketStatus.PENDING_BLOCKAGE_RESOLUTION
    return ticket_id


def test_facility_manager_can_reassign_a_blocked_ticket(auth_client, world):
    """While blocked, the ticket's FM can step in and reassign it, same as the Department POC."""
    other_tech = make_user("tech.ravi", Role.TECHNICIAN, department=world.technical)
    ticket_id = _block_ticket(auth_client, world)

    # A different location's FM has no relationship to this ticket.
    res = act(
        auth_client(world.other_fm), ticket_id, "assign-worker", technician_id=other_tech.id
    )
    assert res.status_code == 404

    # The ticket's own FM can reassign the worker...
    res = act(auth_client(world.fm), ticket_id, "assign-worker", technician_id=other_tech.id)
    assert res.status_code == 200
    assert res.json()["technician"]["id"] == other_tech.id

    # ...or, on a separate blocked ticket, move it to a different department entirely.
    other_ticket_id = _block_ticket(auth_client, world)
    res = act(
        auth_client(world.fm),
        other_ticket_id,
        "change-department",
        department_id=world.it.id,
        note="Actually an IT issue",
    )
    assert res.status_code == 200
    ticket = Ticket.objects.get(pk=other_ticket_id)
    assert ticket.department == world.it
    assert ticket.status == TicketStatus.PENDING_TECHNICIAN_ASSIGNMENT

    # Outside the blockage state, the FM has no such CTA (only the Department POC does).
    ticket_id_3 = raise_ac_ticket(auth_client, world)
    res = act(auth_client(world.fm), ticket_id_3, "assign-worker", technician_id=world.tech.id)
    assert res.status_code == 403


def test_invalid_transitions_are_rejected_with_409(auth_client, world):
    ticket_id = raise_ac_ticket(auth_client, world)
    poc = auth_client(world.tech_poc)

    # Cannot close before a technician has assessed it.
    res = act(poc, ticket_id, "close")
    assert res.status_code == 409
    error = res.json()["error"]
    assert error["code"] == "invalid_transition"
    assert "Pending Technician Assignment" in error["message"]

    # A resolved ticket can't be acted on again.
    assert act(auth_client(world.client), ticket_id, "mark-resolved").status_code == 200
    res = act(poc, ticket_id, "assign-worker", technician_id=world.tech.id)
    assert res.status_code == 409
    assert Ticket.objects.get(pk=ticket_id).status == TicketStatus.RESOLVED


def test_change_department_reroutes_to_new_poc(auth_client, world):
    ticket_id = raise_ac_ticket(auth_client, world)

    res = act(
        auth_client(world.tech_poc),
        ticket_id,
        "change-department",
        department_id=world.it.id,
        note="Network issue, not HVAC",
    )

    assert res.status_code == 200
    assert res.json() == {"id": ticket_id, "visible": False}  # left the old POC's queue
    ticket = Ticket.objects.get(pk=ticket_id)
    assert (ticket.department, ticket.department_poc) == (world.it, world.it_poc)
    last = ticket.activities.last()
    assert (last.from_value, last.to_value, last.comment.body_text) == (
        "Technical",
        "IT",
        "Network issue, not HVAC",
    )
    detail = auth_client(world.it_poc).get(reverse("ticket-detail", args=[ticket_id])).json()
    assert detail["action_required"] is True


def test_new_ticket_is_linked_to_facility_manager_of_office_location(auth_client, world):
    # Acme's office is in Koramangala -> Chandan (fm).
    koramangala_ticket = raise_ac_ticket(auth_client, world)
    assert Ticket.objects.get(pk=koramangala_ticket).facility_manager == world.fm

    # An office in HSR Layout -> Neha (other_fm), with the same department POC.
    hsr_property = Property.objects.create(
        name="HSR Business Centre", code="HSR", location=world.other_fm.location
    )
    office = ClientOffice.objects.create(
        client=Client.objects.create(name="Initech"), property=hsr_property, unit="220"
    )
    Floor.objects.create(office=office, level=1, label="1F")
    hsr_client = make_user("client.initech", Role.CLIENT_POC, client_office=office)
    res = create_ticket(auth_client(hsr_client), title="AC down", issue_type_ids=[world.ac.id])
    body = res.json()
    assert body["facility_manager"]["id"] == world.other_fm.id
    assert body["area"]["name"] == "Bengaluru – HSR Layout"
    assert body["assignees"][0]["id"] == world.other_fm.id

    # Each FM only sees their own location's tickets.
    fm_list = auth_client(world.fm).get(reverse("ticket-list")).json()
    assert [t["id"] for t in fm_list["results"]] == [koramangala_ticket]


def test_only_one_active_facility_manager_per_location(world):
    with pytest.raises(IntegrityError):
        make_user("fm.second", Role.FACILITY_MANAGER, location=world.fm.location)


def test_poc_can_reassign_technician_during_assessment(auth_client, world):
    other_tech = make_user("tech.ravi", Role.TECHNICIAN, department=world.technical)
    ticket_id = raise_ac_ticket(auth_client, world)
    poc = auth_client(world.tech_poc)
    act(poc, ticket_id, "assign-worker", technician_id=world.tech.id)

    res = act(poc, ticket_id, "assign-worker", technician_id=other_tech.id)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == TicketStatus.PENDING_TECHNICIAN_ASSESSMENT
    assert body["technician"]["id"] == other_tech.id
    assert body["action_required"] is False  # waiting on the technician, not the POC
    last = Ticket.objects.get(pk=ticket_id).activities.last()
    assert (last.kind, last.to_value) == (ActivityKind.ASSIGNED_TECHNICIAN, other_tech.display_name)
    # The previous technician loses access.
    detail = reverse("ticket-detail", args=[ticket_id])
    assert auth_client(world.tech).get(detail).status_code == 404
