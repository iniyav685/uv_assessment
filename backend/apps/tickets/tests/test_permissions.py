"""Authorization: data visibility per role and action-level restrictions."""

import pytest
from django.urls import reverse

from .helpers import act, raise_ac_ticket

pytestmark = pytest.mark.django_db


def test_ticket_visibility_is_scoped_by_role(auth_client, world):
    ticket_id = raise_ac_ticket(auth_client, world)
    url = reverse("ticket-detail", args=[ticket_id])

    can_see = [world.client, world.fm, world.tech_poc, world.admin]
    cannot_see = [world.globex_client, world.other_fm, world.it_poc, world.tech]

    for user in can_see:
        assert auth_client(user).get(url).status_code == 200, user.username
    for user in cannot_see:
        res = auth_client(user).get(url)
        assert res.status_code == 404, user.username  # don't leak existence
        assert res.json()["error"]["code"] == "not_found"

    # The technician gains access only once assigned.
    act(auth_client(world.tech_poc), ticket_id, "assign-worker", technician_id=world.tech.id)
    assert auth_client(world.tech).get(url).status_code == 200


def test_only_department_poc_can_assign_worker(auth_client, world):
    ticket_id = raise_ac_ticket(auth_client, world)

    # Facility manager can see the ticket but has no CTA on it.
    res = act(auth_client(world.fm), ticket_id, "assign-worker", technician_id=world.tech.id)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "permission_denied"


def test_poc_cannot_assign_technician_from_another_department(auth_client, world):
    ticket_id = raise_ac_ticket(auth_client, world)
    res = act(
        auth_client(world.tech_poc), ticket_id, "assign-worker", technician_id=world.it_tech.id
    )
    assert res.status_code == 400
    assert "technician_id" in res.json()["error"]["details"]


def test_only_assigned_technician_can_submit_assessment(auth_client, world):
    ticket_id = raise_ac_ticket(auth_client, world)
    act(auth_client(world.tech_poc), ticket_id, "assign-worker", technician_id=world.tech.id)

    res = act(auth_client(world.tech_poc), ticket_id, "submit-assessment", outcome="fully_resolved")
    assert res.status_code == 403


def test_assignee_picker_lists_department_technicians_for_poc_only(auth_client, world):
    ticket_id = raise_ac_ticket(auth_client, world)
    url = reverse("ticket-assignable-users", args=[ticket_id])

    res = auth_client(world.tech_poc).get(url, {"search": "prak"})
    assert res.status_code == 200
    assert [u["id"] for u in res.json()["results"]] == [world.tech.id]  # not the IT technician
    assert auth_client(world.tech_poc).get(url, {"search": "zzz"}).json()["results"] == []

    assert auth_client(world.fm).get(url).status_code == 403  # sees the ticket, can't assign
    assert auth_client(world.globex_client).get(url).status_code == 404
