"""
Load/concurrency checks for the ticket state-transition locking in `services.py`.

Every mutating service function locks the ticket row with `select_for_update`
inside `@transaction.atomic` (see the module docstring there). These tests fire
many real, concurrently-committing transactions at the *same* ticket row —
using `django_db(transaction=True)` so each thread gets its own DB connection
and the locks are real Postgres locks, not the single wrapped transaction the
plain `db` fixture would give us (which would just self-deadlock).

What we're checking for:
  * No lost updates — a transition that should have exactly one winner never
    gets applied twice.
  * Where an action is deliberately re-enterable (e.g. `assign_worker` allows
    reassignment mid-assessment), concurrent calls are still fully serialized
    rather than interleaved/corrupted: every call that logically succeeds
    leaves behind its own activity row and a final state matching whichever
    call the DB actually applied last.
  * No Postgres deadlocks (`deadlock detected`) and no request hangs.
"""

import threading
import time

import pytest
from django.db import IntegrityError, OperationalError, connection

from apps.accounts.models import Role
from apps.common.exceptions import InvalidStateTransition
from apps.tickets import services
from apps.tickets.models import ActivityKind, Ticket, TicketStatus
from conftest import make_user

pytestmark = pytest.mark.django_db(transaction=True)


def _run_concurrently(fns):
    """Run each callable in its own thread, starting them as close together as
    possible, and collect (result, exception) pairs in call order. Each thread
    closes its DB connection on exit so Django doesn't leak them across tests."""
    results = [None] * len(fns)
    barrier = threading.Barrier(len(fns))

    def _target(i, fn):
        try:
            barrier.wait(timeout=5)
            results[i] = (fn(), None)
        except Exception as exc:  # noqa: BLE001 - we want to inspect any exception
            results[i] = (None, exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=_target, args=(i, fn)) for i, fn in enumerate(fns)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
        assert not t.is_alive(), "a thread hung — possible deadlock"
    return results


def _assert_no_deadlocks(results):
    for _, exc in results:
        if exc is not None:
            assert isinstance(exc, InvalidStateTransition), (
                f"expected only InvalidStateTransition for losers, got {exc!r} "
                "(a deadlock or integrity error means the locking is broken)"
            )
            assert not isinstance(exc, (OperationalError, IntegrityError))


def _raise_ticket(world, *, forward=True):
    ticket = Ticket.objects.create(
        client_office=world.acme,
        title="AC blowing warm air",
        primary_issue_type=world.ac,
        description="",
        department=world.technical,
        facility_manager=world.fm,
        created_by=world.client,
    )
    ticket.issue_types.set([world.ac])
    ticket.floors.set(world.floors)
    if forward:
        services.forward_to_department(
            user=world.fm, ticket_id=ticket.id, department=world.technical
        )
    return ticket.id


def test_two_concurrent_forwards_to_different_departments_do_not_both_win(world):
    """forward_to_department is only valid from PENDING_FACILITY_MANAGER_REVIEW and
    leaves it permanently, so a race here has exactly one legitimate winner. Fire the
    FM's forward call to two different departments at once and check only one lands."""
    ticket_id = _raise_ticket(world, forward=False)

    def _forward(department):
        return lambda: services.forward_to_department(
            user=world.fm, ticket_id=ticket_id, department=department
        )

    results = _run_concurrently([_forward(world.technical), _forward(world.it)])
    _assert_no_deadlocks(results)

    successes = [r for r, e in results if e is None]
    failures = [e for _, e in results if e is not None]
    assert len(successes) == 1, f"expected exactly one winner, got {len(successes)}: {results}"
    assert len(failures) == 1
    assert isinstance(failures[0], InvalidStateTransition), failures[0]

    ticket = Ticket.objects.get(pk=ticket_id)
    assert ticket.status == TicketStatus.PENDING_TECHNICIAN_ASSIGNMENT
    assert ticket.department_id in (world.technical.id, world.it.id)
    assert ticket.department_poc_id in (world.tech_poc.id, world.it_poc.id)

    # Only the winner logged a FORWARDED_TO_DEPARTMENT activity — the loser never wrote one.
    assert ticket.activities.filter(kind=ActivityKind.FORWARDED_TO_DEPARTMENT).count() == 1


def test_double_submit_of_the_same_action_is_not_applied_twice(world):
    """Simulates a doubled-up click / retry: the same close() call fired twice
    at once for the same ticket. Only one should actually transition it."""
    ticket_id = _raise_ticket(world)
    services.assign_worker(user=world.tech_poc, ticket_id=ticket_id, technician=world.tech)
    services.submit_assessment(
        user=world.tech, ticket_id=ticket_id, outcome="fully_resolved", comment=""
    )
    assert Ticket.objects.get(pk=ticket_id).status == TicketStatus.PENDING_POC_REVIEW

    def _close():
        return services.close_ticket(user=world.tech_poc, ticket_id=ticket_id, note="Verified.")

    results = _run_concurrently([_close, _close])
    _assert_no_deadlocks(results)

    successes = [r for r, e in results if e is None]
    failures = [e for _, e in results if e is not None]
    assert len(successes) == 1
    assert len(failures) == 1
    assert isinstance(failures[0], InvalidStateTransition)

    ticket = Ticket.objects.get(pk=ticket_id)
    assert ticket.status == TicketStatus.PENDING_CLIENT_CONFIRMATION
    assert ticket.activities.filter(kind=ActivityKind.PENDING_CLIENT_CONFIRMATION).count() == 1


def test_concurrent_reassignment_is_serialized_not_corrupted(world):
    """assign_worker deliberately allows reassigning a different technician while the
    ticket is PENDING_TECHNICIAN_ASSESSMENT (see policies.ALLOWED_FROM) — so unlike the
    tests above, BOTH concurrent calls here are expected to succeed. The race concern
    isn't "who wins" but whether the row lock actually serializes them: without it, two
    threads racing a read-modify-write could stomp on each other and lose an update
    (e.g. only one activity row for two "successful" calls, or a technician value that
    matches neither input). Assert both calls are fully applied and accounted for."""
    ticket_id = _raise_ticket(world)
    other_tech = make_user("tech.ravi", Role.TECHNICIAN, department=world.technical)

    def _assign(technician):
        return lambda: services.assign_worker(
            user=world.tech_poc, ticket_id=ticket_id, technician=technician
        )

    results = _run_concurrently([_assign(world.tech), _assign(other_tech)])
    _assert_no_deadlocks(results)

    successes = [r for r, e in results if e is None]
    assert len(successes) == 2, f"expected both reassignment calls to succeed, got {results}"

    ticket = Ticket.objects.get(pk=ticket_id)
    assert ticket.status == TicketStatus.PENDING_TECHNICIAN_ASSESSMENT
    # Whichever call the DB serialized last decided the final technician — but it must
    # be one of the two inputs, never null/corrupted, and both must be logged.
    assert ticket.technician_id in (world.tech.id, other_tech.id)
    assert ticket.activities.filter(kind=ActivityKind.ASSIGNED_TECHNICIAN).count() == 2


def test_burst_of_concurrent_forward_attempts_produces_no_deadlock_and_one_winner(world):
    """Higher-concurrency version of the two-writer forward test: 10 near-simultaneous
    calls (simulating a retry storm / duplicate requests) racing to forward the same
    ticket. Exactly one wins; nobody raises a DB-level deadlock error, and it stays fast
    rather than hanging on lock contention."""
    ticket_id = _raise_ticket(world, forward=False)

    def _forward():
        return services.forward_to_department(
            user=world.fm, ticket_id=ticket_id, department=world.technical
        )

    start = time.monotonic()
    results = _run_concurrently([_forward] * 10)
    elapsed = time.monotonic() - start
    _assert_no_deadlocks(results)

    successes = [r for r, e in results if e is None]
    assert len(successes) == 1, f"expected exactly one winner among 10, got {results}"
    assert elapsed < 8, f"took {elapsed:.2f}s — looks like lock contention/starvation, not just queuing"

    ticket = Ticket.objects.get(pk=ticket_id)
    assert ticket.status == TicketStatus.PENDING_TECHNICIAN_ASSIGNMENT
    assert ticket.activities.filter(kind=ActivityKind.FORWARDED_TO_DEPARTMENT).count() == 1
