# Concurrency / race-condition load test

Scope: verify whether the ticket state-transition code (`backend/apps/tickets/services.py`)
and its notification fan-out (`backend/apps/notifications/tasks.py`) hold up under
concurrent requests — specifically, whether two racing writers on the same ticket can
deadlock the database or produce a lost/corrupted update.

## Approach

Every mutating ticket action locks the ticket row with `select_for_update` inside
`@transaction.atomic` (`services.py:77-82`), which is the mechanism meant to prevent two
concurrent requests from both applying a transition. Rather than just reading that code
and trusting it, `backend/apps/tickets/tests/test_concurrency.py` fires real, concurrently
**committing** transactions at the same ticket row and checks the outcome.

This uses `pytest.mark.django_db(transaction=True)` (not the default `db` fixture), which
matters: the plain `db` fixture wraps a whole test in one outer transaction, so "concurrent"
threads would just block on that single wrapping transaction and never exercise a real
Postgres lock. `transaction=True` gives each thread its own connection and lets writes
actually commit, so `select_for_update` contention between threads is real.

Each test spins up N threads, releases them at the same instant with a `threading.Barrier`,
and collects `(result, exception)` per thread. A thread that hangs past a 10s join is a
deadlock; an `OperationalError`/`IntegrityError` instead of the expected
`InvalidStateTransition` means the locking is broken, not just contended.

Run it:

```
docker compose exec backend python -m pytest apps/tickets/tests/test_concurrency.py -v
```

(Run inside the `backend` container, not on the host — the host's `localhost:6379`/`5433`
aren't the addresses the app is configured with; see "Gotcha" below.)

## Findings — ticket row locking: no bugs found

Four scenarios were tested against real Postgres:

| Test | Scenario | Result |
|---|---|---|
| `test_two_concurrent_forwards_to_different_departments_do_not_both_win` | Two threads race `forward_to_department` to different departments on the same ticket | Exactly one wins, the other gets `InvalidStateTransition` (409), no deadlock |
| `test_double_submit_of_the_same_action_is_not_applied_twice` | The same `close_ticket` call fired twice at once (double-click / client retry) | Applied exactly once |
| `test_concurrent_reassignment_is_serialized_not_corrupted` | Two threads race `assign_worker` with different technicians (this action is deliberately re-enterable — POCs can reassign mid-assessment) | Both calls succeed, but **serialized**, not interleaved: 2 activity rows, final `technician` is one of the two inputs, never null/corrupted |
| `test_burst_of_concurrent_forward_attempts_produces_no_deadlock_and_one_winner` | 10 threads race `forward_to_department` on one ticket (retry-storm simulation) | Exactly 1 winner, 9 clean 409s, completes in well under a second |

**Conclusion:** the `select_for_update` + `@transaction.atomic` pattern in `services.py`
does what its module docstring claims. No lost updates, no deadlocks, no corrupted state
under direct contention on a single ticket row.

One thing worth knowing for future test-writing: `assign_worker` is *intentionally*
re-enterable from `PENDING_TECHNICIAN_ASSESSMENT` (see `policies.ALLOWED_FROM`) — a first
draft of this test assumed only one concurrent `assign_worker` call could ever win, which
is wrong and produced false failures. Actions with exactly one valid source status
(`forward_to_department`, `close`) are the ones to reach for when a test needs a
guaranteed single winner.

## Finding — a real race in async notification fan-out

Testing the DB layer raised a related question: when a technician is reassigned quickly,
is the *first* technician's notification cleanly reverted? The answer is mixed:

- **Access** is fine: ticket visibility for a technician is a live query
  (`technician=user`), so a reassigned-away technician loses access immediately.
- **A failed/rolled-back transition** is also fine: `enqueue_activity_notifications` defers
  sending via `transaction.on_commit` (`dispatch.py:41`), so a losing racer's transaction
  rollback means its notification is simply never queued.
- **A successful-but-quickly-superseded transition was not fine.** `recipients_for()`
  (`notifications/tasks.py`) computed who to notify by reading the ticket's **live**
  `technician_id`/`department_poc_id` at the time the Celery worker processed the task —
  not the state at the moment that specific activity happened. Notification delivery is
  async (`transaction.on_commit` → `notify_activity.delay(...)`), so there is a real gap
  between "activity committed" and "task executed," and that gap grows with queue backlog
  — exactly the condition a load test is meant to surface.

### Reproduction

Assign technician A, then immediately reassign to technician B, then inspect what the
*first* activity's (A's assignment) notification would send:

```
activity1 meta (snapshot of assignment A): {'assignee_id': 48}   # A
recipients_for(act1) [BEFORE FIX]: {45, 15}                      # 45 = B, not A!
message for 45: "Abdul Rahman assigned Farah Rao (A) to #TKT-1744..."
```

Effects of the bug:
- **Technician A never got notified** they were ever assigned — dropped from the recipient
  set by the time the task ran.
- **Technician B got a duplicate, confusing notification** for an event that wasn't about
  them, worded as if A were still the assignee (`build_message`'s `is_assignee` check
  compares the activity's frozen `meta["assignee_id"]` against the *live* recipient, so it
  silently took the wrong branch).

The same staleness applied to `FORWARDED_TO_DEPARTMENT` and `CHANGED_DEPARTMENT`, which
also carry a `meta["assignee_id"]` snapshot of who was routed to, read against the live
`department_poc_id`.

### Fix

`recipients_for()` now overrides the specific field an activity assigns with that
activity's own `meta["assignee_id"]` snapshot instead of the ticket's live value, for the
three kinds where staleness was possible:

```python
_ASSIGNEE_OVERRIDES = {
    ActivityKind.ASSIGNED_TECHNICIAN: "technician_id",
    ActivityKind.FORWARDED_TO_DEPARTMENT: "department_poc_id",
    ActivityKind.CHANGED_DEPARTMENT: "department_poc_id",
}
```

Other stakeholder fields (creator, facility manager) are untouched — they don't change
within the scope of these actions, so the live read was never the problem there. `AUTO_ASSIGNED`
also didn't need this: the facility manager is set once at ticket creation and never
reassigned afterward.

After the fix, the same reproduction above resolves correctly:

```
recipients_for(act1) [AFTER FIX]: {48, 15}                       # 48 = A, correct
message for 48: "Abdul Rahman assigned you to #TKT-1744..."
```

### Regression tests

Added to `backend/apps/notifications/tests/test_tasks.py`:
- `test_reassignment_before_the_first_notification_runs_still_targets_the_original_technician`
- `test_reroute_before_the_first_notification_runs_still_targets_the_original_poc`

Both construct the exact race (second transition committed before the first activity's
`recipients_for()` is evaluated) and assert the original assignee/POC — not whoever holds
the ticket now — is the one notified.

## Scope not covered

- This was a service-layer concurrency test, not an HTTP-level load test — no load was put
  on the DRF views, auth, or gunicorn/ASGI stack itself. If throughput/latency under many
  simultaneous *HTTP* clients matters, that's a separate tool (e.g. Locust/k6) hitting the
  running `docker compose` stack.
- Only single-ticket, single-action-type races were tested. A compound race across two
  *different* action types on the same ticket (e.g. `assign_worker` racing
  `change_department`) is a much rarer scenario and wasn't tested; the notification fix
  is intentionally scoped to the field each action kind actually owns rather than trying to
  snapshot every ticket field for every activity.
- The Celery/Redis broker itself wasn't put under load — the notification race was
  reproduced by direct sequencing (call the service functions in an order that mimics a
  backlogged queue), not by actually saturating Redis/Celery.

## Gotcha: run tests inside the backend container

Running `pytest` from the host machine's venv fails at test teardown with

```
redis.exceptions.ConnectionError: Error 61 connecting to localhost:6379. Connection refused.
```

because `docker-compose.yml` doesn't publish Redis to the host — only Postgres (`5433`) and
the app (`8000`) are. Use `docker compose exec backend python -m pytest ...` so the test
process runs with the container's `REDIS_URL`/`DATABASE_URL` (pointing at the `redis`/`db`
service names on the compose network), matching how the app actually runs.
