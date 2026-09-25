"""List API: pagination, filtering, search, sorting and query efficiency."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.tickets.models import Ticket

from .helpers import act, create_ticket

pytestmark = pytest.mark.django_db


@pytest.fixture
def many_tickets(auth_client, world):
    client = auth_client(world.client)
    for i in range(12):
        issue = world.ac if i % 3 else world.internet
        res = create_ticket(
            client,
            title=f"{issue.name} #{i}",
            issue_type_ids=[issue.id],
            floor_ids=[world.floors[0].id],
        )
        ticket_id = res.json()["id"]
        Ticket.objects.filter(pk=ticket_id).update(created_at=timezone.now() - timedelta(days=i))
    return world


def list_tickets(api, **params):
    res = api.get(reverse("ticket-list"), params)
    assert res.status_code == 200, res.json()
    return res.json()


def test_pagination_and_sorting(auth_client, many_tickets):
    admin = auth_client(many_tickets.admin)

    page1 = list_tickets(admin, page_size=5)
    assert (page1["count"], page1["total_pages"], len(page1["results"])) == (12, 3, 5)
    newest = [t["created_at"] for t in page1["results"]]
    assert newest == sorted(newest, reverse=True)

    oldest = list_tickets(admin, page_size=5, ordering="created_at")["results"]
    assert oldest[0]["created_at"] < newest[-1]

    res = admin.get(reverse("ticket-list"), {"page": 99})
    assert res.status_code == 404


def test_filters_search_and_tabs(auth_client, many_tickets):
    w = many_tickets
    admin = auth_client(w.admin)

    it_only = list_tickets(admin, department=w.it.id)
    assert it_only["count"] == 4
    assert {t["department"]["name"] for t in it_only["results"]} == {"IT"}

    assert list_tickets(admin, client=w.globex.client_id)["count"] == 0
    assert list_tickets(admin, facility_manager=w.fm.id)["count"] == 12
    assert list_tickets(admin, search="internet")["count"] == 4

    first = Ticket.objects.order_by("id").first()
    assert list_tickets(admin, search=first.number)["results"][0]["id"] == first.id

    act(auth_client(w.client), first.id, "mark-resolved")
    assert list_tickets(admin, tab="closed")["count"] == 1
    assert list_tickets(admin, tab="open", status="resolved")["count"] == 0
    assert admin.get(reverse("ticket-counts")).json() == {"open": 11, "closed": 1}

    res = admin.get(reverse("ticket-list"), {"status": "bogus"})
    assert res.status_code == 400


def test_list_query_count_does_not_grow_with_page_size(auth_client, many_tickets):
    admin = auth_client(many_tickets.admin)

    def count_queries(page_size):
        with CaptureQueriesContext(connection) as ctx:
            list_tickets(admin, page_size=page_size)
        return len(ctx.captured_queries)

    assert count_queries(2) == count_queries(12)
