from django.urls import reverse


def create_ticket(client, **payload):
    return client.post(reverse("ticket-list"), payload, format="json")


def act(client, ticket_id, action, **payload):
    return client.post(reverse(f"ticket-{action}", args=[ticket_id]), payload, format="json")


def raise_ac_ticket(auth_client, world, *, forward: bool = True) -> int:
    """Raises an AC ticket for Acme (Koramangala). By default the FM immediately forwards
    it to Technical, since most tests exercise what happens after routing, not the FM step
    itself. Pass forward=False to test the ticket while still pending the FM's review."""
    res = create_ticket(
        auth_client(world.client),
        title="AC blowing warm air",
        issue_type_ids=[world.ac.id],
        floor_ids=[f.id for f in world.floors],
    )
    assert res.status_code == 201, res.json()
    ticket_id = res.json()["id"]
    if forward:
        res = act(
            auth_client(world.fm),
            ticket_id,
            "forward-to-department",
            department_id=world.technical.id,
        )
        assert res.status_code == 200, res.json()
    return ticket_id
