# Helpdesk — Facility Ticket Management

A full-stack ticketing system for a managed-office operator. Clients raise facility issues
(AC not cooling, internet down, and so on). Each ticket is automatically routed to the right
department's POC, who assigns a technician. The technician submits an assessment, and the POC
reviews it and closes the ticket.

**Stack:** React 19 + Material UI + TanStack Query (native `fetch`) + React Router + TipTap ·
Django 5.2 + DRF · PostgreSQL 16 · Redis 7 · Celery 5 (default worker + dedicated notifications
worker + beat) · S3 (SeaweedFS locally) ·
Docker Compose

---

## Contents

1. [Quick start](#quick-start)
2. [Demo walkthrough](#demo-walkthrough)
3. [Running tests](#running-tests)
4. [API](#api)
5. [Data model](#data-model)
6. [Ticket lifecycle](#ticket-lifecycle-state-machine)
7. [Authorization](#authorization)
8. [Architecture decisions](#architecture-decisions)
9. [Engineering depth](#engineering-depth)
10. [Celery and Redis design](#celery-and-redis-design)
11. [Assumptions](#assumptions)
12. [Limitations and future improvements](#limitations-and-future-improvements)
13. [AWS deployment note](#aws-deployment-note)
14. [Time spent](#time-spent)

---

## Quick start

**Prerequisites:** Docker with Compose v2 (Docker Desktop, Colima or OrbStack) for the backend
services, and Node 22+ for the frontend, which runs directly on the host (not in Docker).

```bash
cp .env.example .env
docker compose up --build       # db, redis, s3, backend, worker, worker-notifications, beat
cd frontend && npm install && npm run dev
```

| Service  | URL                               |
|----------|-----------------------------------|
| App      | http://localhost:5173             |
| API      | http://localhost:8000/api/        |
| Admin    | http://localhost:8000/admin/      |
| Health   | http://localhost:8000/api/health/ |
| Local S3 | http://localhost:8333 (SeaweedFS, S3 API) |

When the backend container starts, it applies migrations and loads the sample data
(`SEED_DATA=1`). You don't need to do anything else.

```bash
make seed                                                    # re-run the seed (idempotent)
docker compose exec backend python manage.py seed_data --reset   # regenerate all tickets
make logs                                                    # follow the backend and worker logs
```

The seed creates 19 users, 3 locations, 3 properties, 5 client offices, 4 departments,
10 issue types and 64 tickets. The tickets are spread across every status and the last six weeks, so pagination,
filters, search and both tabs all have something to show. The data uses a fixed random seed,
so every run produces the same result.

### Demo accounts

All accounts use the password `demo12345!`. With `DEMO_MODE=True`, the login page shows each
one as a one-click chip.

| Username         | Role (wireframe persona)                | Sees                                   |
|------------------|-----------------------------------------|----------------------------------------|
| `client.acme`    | Client POC — Chaitanya M (Acme Corp)    | All Acme tickets                       |
| `fm.chandan`     | Facility Manager — Koramangala          | Tickets in their location              |
| `fm.neha`        | Facility Manager — HSR Layout           | Tickets in their location              |
| `poc.technical`  | Department POC — Technical Manager      | Tickets routed to Technical            |
| `poc.it`         | Department POC — IT Manager             | Tickets routed to IT                   |
| `tech.prakash`   | Technician (Technical)                  | Tickets assigned to him                |
| `client.globex`  | Client POC (Globex)                     | All Globex tickets                     |
| `admin`          | Admin (also Django admin)               | Everything                             |

## Demo walkthrough

This follows the wireframe in order:

1. **Client creates a ticket.** Sign in as `client.acme` and click **Create New Ticket**. Enter a
   title and add issue tags (quick-issue chips add a tag and fill an empty title). The first tag
   decides the department. Floors are required because Acme's office has two. After submitting,
   the ticket opens in a modal with *"Ticket created successfully… Mark Resolved"*.
2. **Department POC acts.** Sign in as `poc.technical`. The ticket shows an **Action Required**
   badge. Open it and click the **Assignee** field in the right panel to search and pick a
   technician (or use **Assign Worker** / **Change Department** in the CTA panel).
3. **Facility Manager watches.** `fm.chandan` can see the ticket and its activity but has no
   actions (the wireframe's "no CTA").
4. **Technician assesses.** Sign in as `tech.prakash` and click **Submit Assessment**. Choose
   *Fully Resolved* (moves to *Pending Department POC Review*), or *Partially Resolved* /
   *Suggest Department/Worker Change* (moves to *Pending Blockage Resolution*; a comment is
   required).
5. **POC reviews.** Back as `poc.technical`, **Close Ticket** or reassign it.
6. At any open stage, the client can **Mark Resolved**. Every step appears in the activity
   feed, and the other stakeholders get a notification (the bell in the header).

## Running tests

```bash
docker compose exec backend pytest            # 33 backend tests (runs against PostgreSQL)
cd frontend && npm install && npm test        # 13 frontend tests (Vitest + Testing Library)
```

| Area | What the tests protect |
|---|---|
| Business rules | One ticket per issue with auto-routing; the full lifecycle; comment required for partial resolution; **invalid transitions return 409** and leave state unchanged; department change reroutes to the new POC |
| Authorization | Role-scoped visibility (404 for tickets you can't see); FM gets **403** on POC actions; POC can't assign a technician from another department; only the assigned technician can assess |
| Celery task | Stakeholders are notified (not the actor); enqueued only after commit; **duplicate execution is idempotent**; transient failure is **retried then succeeds**; exhausted retries fail but keep in-app notifications |
| Comments & attachments | HTML sanitising strips scripts/handlers; presign → upload → attach flow; type/size limits; can't attach unfinished or someone else's upload; orphan cleanup deletes only stale pending uploads and is idempotent (S3 faked with moto) |
| Location routing | New ticket links to the FM of the office's location; each FM sees only their location; one active FM per location (DB constraint) |
| List API | Pagination, sorting, each filter, search (including by ticket number), tabs, counts, rejecting unknown statuses, and **query count independent of page size** |
| Frontend | Login validation and duplicate-submit guard; list renders API data and syncs sort, tab and filters to query params and the URL; action panel CTAs by role, client-side validation, and showing the server's 409 message |

## API

All endpoints are under `/api/` and use JSON. Authentication uses
`Authorization: Bearer <access>`.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/auth/login/` | `{username, password}` → `{access, refresh}` (rate-limited 10/min) |
| POST | `/auth/refresh/` | `{refresh}` → `{access}` |
| GET | `/auth/me/` | Current user with role and `can_create_ticket` |
| GET | `/auth/demo-accounts/` | Demo logins (empty unless `DEMO_MODE`) |
| GET | `/lookups/` | Departments, clients, FMs, statuses, issue types, the user's offices and floors, and technicians. One request per session. |
| GET | `/tickets/` | Paginated list. Query: `tab=open\|closed`, `search`, `client`, `department`, `facility_manager`, `status` (comma-separated), `ordering=created_at\|-created_at`, `page`, `page_size` (max 100) |
| GET | `/tickets/counts/` | `{open, closed}` for the current filters (used for the tab labels) |
| POST | `/tickets/` | Create. `{client_office_id?, title, issue_type_ids[] (tags; first = primary), floor_ids[], description}` → `201` ticket |
| GET | `/tickets/{id}/` | Detail, including `activities` and `available_actions` |
| GET | `/tickets/{id}/assignable-users/?search=` | Jira-style assignee picker: the department's technicians (Department POC only) |
| POST | `/tickets/{id}/assign-worker/` | `{technician_id}` — Department POC (also reassigns during assessment) |
| POST | `/tickets/{id}/change-department/` | `{department_id, note}` — Department POC |
| POST | `/tickets/{id}/submit-assessment/` | `{outcome, comment}` — assigned technician |
| POST | `/tickets/{id}/close/` | `{note?}` — Department POC, after assessment |
| POST | `/tickets/{id}/mark-resolved/` | Creator or client POC |
| POST | `/tickets/{id}/attachments/` | `{filename, content_type, size}` → `201 {id, upload: {url, fields}}` presigned S3 POST |
| POST | `/tickets/{id}/comments/` | `{body (rich-text HTML), attachment_ids[]}` → `201` with the updated ticket |
| GET | `/notifications/` | The user's notifications plus `unread_count` |
| POST | `/notifications/{id}/read/`, `/notifications/read-all/` | Mark as read |
| GET | `/health/` | Liveness and database check |

Actions return the updated ticket, so the client writes it straight to its cache instead of
refetching.

**Error envelope.** Every error has the same shape:

```json
{ "error": { "code": "invalid_transition",
             "message": "Cannot close the ticket while the ticket is 'Pending Technician Assignment'." } }
{ "error": { "code": "validation_error", "message": "Some fields are invalid.",
             "details": { "floor_ids": ["Select at least one floor."] } } }
```

| Status | Meaning |
|---|---|
| 400 | Validation (`details` holds field errors) |
| 401 | Not authenticated |
| 403 | Can see the ticket but may not perform this action |
| 404 | Doesn't exist, or not visible to you (existence isn't leaked) |
| 409 | Invalid state transition |
| 429 | Throttled |
| 500 | Unexpected error: logged with a traceback, returned as a generic message |

## Data model

```
Location ──< Property ──< ClientOffice ──< Floor           Department ──< IssueType
   ▲                          │  client → Client               │ poc → User
   │ location                 │
 User (role enum: client_poc | facility_manager | department_poc | technician | admin)
   ▲  created_by / department_poc / technician / facility_manager / closed_by
   │
Ticket ──< TicketActivity ──(0..1)── TicketComment ──< Attachment (S3 object)
  │              └──< Notification
  └── floors (M2M Floor)
```

- **User** — one table for everyone; `role` is an enum. Client POCs belong to a
  `ClientOffice`; POCs and technicians to a `Department`; Facility Managers to a `Location`.
- **Location → Property → ClientOffice → Floor** — where the issue is. `Client` is its own table.
- **Routing at creation**
  - *Department POC* = `Department.poc` of the issue's department (auto-assigned).
  - *Facility Manager* = the active FM whose `location` is the office's location (auto-linked,
    stored on `Ticket.facility_manager`). A partial unique constraint allows **one active FM
    per location**, so this is never ambiguous.
- **Ticket** has a free-text `title` and **issue types as tags** (`issue_types` M2M). The first
  tag is stored as `primary_issue_type` and decides the department. It stores current routing
  (`department`, `department_poc`, `technician`, `facility_manager`) and `status`. Routing values are snapshots, so reassigning a POC/FM later
  doesn't silently move existing tickets.
- **TicketActivity** — append-only audit trail (actor, kind, from → to, meta, timestamp). If the
  event carries text (a comment, forwarding note, assessment comment or closing note), it links
  one-to-one to a **TicketComment**, which has its own FK to Ticket.
- **TicketComment** — sanitised rich-text `body_html` + plain `body_text` (previews/search).
- **Attachment** — a private S3 object (`storage_key`, name, type, size) with status `pending`
  (presigned URL issued) → `attached` (verified in the bucket and linked to a comment).
- **Notification** — one row per (activity, recipient), written by the Celery worker.

**Database constraints** (enforced in PostgreSQL):

- Users: valid role; client POC needs an office; POC/technician need a department; FM needs a
  location; one active FM per location.
- Ticket: valid status; technician required during assessment; `closed_at` set exactly when
  Resolved/Closed.
- Activity: valid kind; a "commented" event must reference a comment.
- Attachment: valid status, `size > 0`, `attached` ⇒ linked to a comment; unique storage key.
- Uniqueness: (city, area) per location, unit per property, floor level per office,
  notification per (activity, recipient) — the last makes the Celery task idempotent.
- `PROTECT` on history-bearing foreign keys, so deleting a user/department can't cascade away
  tickets.

**Indexes and why**

| Index | Serves |
|---|---|
| `ticket(status, -created_at)` | Default list: Open/Closed tab sorted by time |
| `ticket(department, status)` | Department POC queue |
| `ticket(technician, status)` | Technician queue |
| `ticket(facility_manager, status)` | Facility Manager's location view |
| `ticket_activity(ticket, created_at)`, `ticket_comment(ticket, created_at)` | Timeline in order |
| `attachment(status, created_at)` | Hourly orphaned-upload cleanup |
| `notification(recipient, is_read)` | Unread badge (polled every 30 s) |

## Ticket lifecycle (state machine)

| Action (who) | Allowed from | Result |
|---|---|---|
| create (client, FM, POC) | — | **Pending Technician Assignment**; routed by the **first issue tag** to that department's POC; linked to the location's FM |
| assign / reassign worker (POC) | Pending Tech. Assignment, Pending Tech. Assessment, Pending POC Review, Pending Blockage | **Pending Technician Assessment** |
| change department (POC) | same as above | **Pending Technician Assignment** in the new department; technician cleared |
| submit assessment (technician) | Pending Technician Assessment | Fully resolved → **Pending Department POC Review**; partial or reassign → **Pending Blockage Resolution** |
| close (POC) | Pending POC Review, Pending Blockage | **Closed** |
| mark resolved (creator or client) | any open status | **Resolved** |
| comment (anyone who can see it) | any open status | — |

The rules live in one table (`apps/tickets/policies.py::ALLOWED_FROM`). Every write goes
through `apps/tickets/services.py`, which locks the row (`SELECT … FOR UPDATE`), re-checks
permission and state, updates the ticket and writes the activity in one transaction.

## Authorization

| Role | Can see | Can do |
|---|---|---|
| Client POC | All tickets for their client company | Create (multiple issues allowed; description optional), mark resolved, comment |
| Facility Manager | Tickets auto-linked to them (their location), plus any they raised | Create for offices in their location (one issue, description required), comment. No workflow actions. |
| Department POC | Tickets routed to their department, plus any they raised | Assign worker, change department, close, create, comment |
| Technician | Tickets currently assigned to them | Submit assessment, comment |
| Admin | Everything | Everything |

- **Visibility** is applied to the queryset, so a ticket you can't see returns **404** rather
  than 403. This avoids revealing that it exists.
- **Actions** are checked for permission first (**403**) and then state (**409**).
- The API returns `available_actions` for each ticket, and the React action panel is built
  entirely from that list. The UI never offers an action the API would reject, and the rules
  exist in only one place.

## Architecture decisions

- **Service layer for writes.** Views only parse input and shape output. All business rules
  (permission, state, side effects) sit in `services.py`, which keeps them testable and stops
  views from drifting apart.
- **Free-text title + issue tags.** Users write their own title; issue types are tags picked
  from a dropdown (quick-issue chips add a tag and autofill an empty title). A ticket can carry
  several tags; the **first** is the primary issue and decides the department, and the POC can
  still use Change Department.
- **Jira-style ticket modal.** `/tickets/:id` opens as a modal over the list (the list keeps its
  filters). Left: CTA panel, description, activity; right: a details panel with Assignee, Tags,
  Department POC, Facility Manager, Reporter, Department, Client, Location and dates. For the
  Department POC, clicking the assignee opens a server-side searchable list of the department's
  technicians and assigns on click; for everyone else it's read-only. Reassigning while an
  assessment is pending is allowed but doesn't mark the ticket "Action Required" for the POC.
- **JWT (SimpleJWT)** because in production the SPA and API sit on separate origins.
- **React Query + native `fetch`, no axios.** React Query owns caching, retries and request
  state; a ~100-line `fetch` client adds the base URL, JSON, bearer token, a single shared token
  refresh on 401, timeouts and the `ApiError` mapping. File uploads use `XMLHttpRequest` only
  because `fetch` can't report upload progress.
- **Rich text with TipTap** (ProseMirror). Chosen over Quill because `react-quill` is
  unmaintained and incompatible with React 19. HTML is sanitised server-side with `nh3` against a
  tag allow-list and again in the browser with DOMPurify.
- **Direct-to-S3 uploads.** The API issues a presigned POST whose policy pins the key, content
  type and max size; the browser uploads straight to the bucket (large files never pass through
  Django). On comment submit the server `HEAD`s each object before linking it, and records the
  stored size rather than the client's claim. Reads use short-lived presigned GET URLs; the
  bucket stays private.
- **The URL is the source of truth for list state.** Tab, search, filters, sort and page live
  in the query string: they survive reloads, can be shared, and back/forward works. React Query
  keys come from the same parameters, which gives caching and deduplication.
  `keepPreviousData` prevents flicker between pages.
- **Avoiding unnecessary fetching and re-rendering.** Lookups load once per session (10-minute
  stale time). Mutation responses are written straight into the detail cache (no refetch).
  Search is debounced. Filters are edited as a draft and applied in one go. List rows use
  `React.memo`.
- **Feature-based frontend structure.** `features/{auth,tickets,notifications}` each contain
  their API hooks and components. Shared UI (`LoadingState`, `EmptyState`, `ErrorState`,
  `ConfirmDialog`, `UserAvatar`, `PageHeader`) lives in `components/`.
- **Duplicate-submission protection.** Every submit button is disabled while its request is in
  flight, and the handlers also return early if a request is already pending. On the server,
  the row lock plus state check means a repeated transition fails with 409 instead of being
  applied twice.

## Engineering depth

The brief asks for two of these; all four are implemented:

1. **Audit history.** `TicketActivity` records every change with actor, timestamp, action and
   from→to values. It powers the wireframe's ACTIVITY feed (with the All / Actions / Comments
   filter) and is read-only in the Django admin.
2. **Transactions.** Every service function is `@transaction.atomic` with `select_for_update`.
   Ticket creation writes the ticket, floor links and two activity rows, repeated per issue,
   atomically. Notifications are enqueued with `transaction.on_commit`, so a rolled-back
   change never sends one.
3. **Query optimization.** The list uses `select_related` for seven relations
   (office→client, office→property→location, department, POC, technician, facility manager,
   creator)
   and `prefetch_related` for floors. The detail view adds a `Prefetch` of activities with
   their actors. A page therefore costs a fixed number of queries whatever its size; a test
   asserts this. `/tickets/counts/` uses a single conditional aggregation
   (`Count(filter=Q(...))`) instead of two COUNT queries.
4. **Logging.** Structured `key=value` log lines for every transition
   (`ticket.transition action=… ticket_id=… user_id=… from=… to=…`) and for every task run and
   failure. Only IDs and enum values are logged: never descriptions, comments, e-mail
   addresses or tokens.

## Celery and Redis design

**What runs asynchronously.** When an activity is recorded, `notify_activity(activity_id)`
fans out notifications to the ticket's stakeholders (creator, current POC and technician,
excluding the person who acted; the client POC of the ticket's office is added in when a
technician marks a ticket fully resolved, so they're asked to verify). It creates in-app
`Notification` rows and sends a simulated e-mail. Redis is the broker and result backend.

**Its own queue and worker.** `notify_activity` is routed to a dedicated `notifications`
Celery queue, consumed only by the `worker-notifications` service (`docker-compose.yml`);
`cleanup_orphan_attachments` and everything else stay on the `default` queue, consumed by
`worker`. Same codebase, database and broker — just a separate deployable/scalable process —
so a mail-provider slowdown or a burst of retries never delays unrelated tasks, and either
worker can be scaled independently of the other.

**Reliability:**

- Enqueued via `transaction.on_commit`, so the worker never sees uncommitted data.
- If the broker is down when enqueueing, the error is logged and the API call still succeeds.
  The activity is already recorded and can be re-dispatched.
- `acks_late=True` and `reject_on_worker_lost=True`: if a worker crashes mid-task, the message
  is redelivered instead of lost. `prefetch_multiplier=1` and time limits are set.
- **Retries:** `autoretry_for=(TransientDeliveryError, OperationalError)` with exponential
  backoff and jitter, up to 4 retries. After that, `on_failure` logs the failure. The in-app
  notifications already exist, and only the e-mail is missing (`emailed_at IS NULL`), so it can
  be re-sent later.
- An activity that no longer exists isn't retried (there's nothing to recover).
- Set `NOTIFICATION_SIMULATED_FAILURE_RATE=0.3` in `.env` and restart the worker to watch
  retries happen in `make logs`.

**Periodic job (Celery beat).** `cleanup_orphan_attachments` runs hourly and removes uploads
that were never attached to a comment (older than 24 h). Each row is deleted with a
`status=pending` re-check and the S3 delete happens inside the same transaction, so an upload
attached in the meantime is never touched and a failed S3 call rolls back to be retried. Only
one beat instance should run.

**Duplicate execution.** Late acks and retries mean the same task can run more than once.
This is safe for two reasons:

1. Rows are created with `get_or_create` on the **unique (activity, recipient)** constraint,
   so a second run, even a concurrent one, can't create duplicates.
2. An e-mail is sent only for rows where `emailed_at IS NULL`, and `emailed_at` is set with a
   conditional `UPDATE … WHERE emailed_at IS NULL`, so each recipient is e-mailed once.

Both paths are covered by tests.

## Assumptions

Where the wireframe didn't specify a rule, I assumed the following:

- **Roles and mapping.** "Concerned Facility Manager" is the FM of the property where the
  client office is located. "Concerned Department" is the department the issue type belongs to.
- **Creation forms.** Clients may pick several issues with an optional description. Internal
  users pick a client (only when they have more than one), then a single issue, and must write
  a description. This matches the two forms in the wireframe. Floors are asked for only when
  the office has more than one floor; single-floor offices get their floor automatically.
- **Auto-assignment.** A new ticket is assigned to the department POC by "System", shown as
  two activity events as in the wireframe.
- **After the technician.** The wireframe stops at *Pending Department POC Review*. I added a
  minimal review step: the POC can close the ticket or reassign it (worker or department).
  *Partially Resolved* and *Suggest Change* lead to *Pending Blockage Resolution*, which puts
  the ticket back in the POC's queue.
- **Closing.** The client or creator can **Mark Resolved** at any open stage, as the wireframe
  shows on every client screen. Closed tickets are read-only (no comments).
- **Visibility after rerouting.** After a department change, the old POC loses visibility (the
  wireframe says "the new Department POC will start seeing the ticket"). A reassigned
  technician likewise loses access.
- **Current Assignee(s)** shows the department POC plus the technician when one is assigned,
  matching the wireframe.
- **"Action Required"** marks tickets waiting on *you* specifically.
- **Filters** are multi-select. **Sort** is by creation time, newest first by default.
- **Ticket numbers** (`TKT-1042`) are derived from the primary key, and search understands them.

## Limitations and future improvements

- **Tokens** are kept in `localStorage` for simplicity. In production I would use an httpOnly,
  SameSite refresh-token cookie with the access token held in memory.
- **Notifications** use 30-second polling. With more time I'd push them over WebSockets
  (Django Channels) or SSE, and send real e-mail through SES.
- **Search** uses `icontains`. At scale I'd switch to PostgreSQL full-text search (a
  `SearchVector` with a GIN index) or `pg_trgm`.
- **Lookups** return all reference data in one call. With thousands of clients this should
  become an async, paginated autocomplete endpoint.
- **Attachments** are shown below a comment rather than inline in the rich text (inline images
  would embed presigned URLs that expire). No virus scanning yet — in production an S3 event →
  Lambda/ClamAV step would quarantine files before they're served.
- **No SLA timers or escalation** (for example a Celery beat job flagging tickets stuck in a
  status).
- **Frontend bundle** is a single ~250 kB gzipped chunk. Route-level code splitting would
  reduce the first load.
- **E2E tests.** I walked through the flow by hand in Playwright while developing. A committed
  Playwright suite in CI would be the next step.
- Optimistic concurrency (ETags) for the detail view, and an admin UI for managing reference
  data, are outside the brief.

## AWS deployment note

A live deployment isn't required. In short: **ECS Fargate** for the web/worker/beat services behind
an **ALB**, **RDS PostgreSQL** (Multi-AZ) for the database, **ElastiCache for Redis** as the
broker/cache, the SPA on **S3 + CloudFront**, ticket attachments in a private S3 bucket via
presigned URLs, secrets in **Secrets Manager**, and CI/CD through GitHub Actions → ECR → ECS.

Full breakdown (compute, database, networking, scaling, monitoring, failure recovery, CI/CD):
see [docs/AWS_DEPLOYMENT.md](docs/AWS_DEPLOYMENT.md).

## Time spent

~8 hours total.

---

### Project structure

```
backend/
  config/                 settings (env-driven), urls, celery app
  apps/common/            error envelope, pagination, health, S3 storage, rich-text sanitiser,
                          seed_data / ensure_bucket commands
  apps/accounts/          custom User + roles, JWT login, demo accounts
  apps/organizations/     Location, Property, Client, ClientOffice, Floor, Department, IssueType
  apps/tickets/           models, policies (authz + state machine), routing, services, filters,
                          comments/attachments API, cleanup task
  apps/notifications/     Notification model, Celery task, delivery, API
frontend/src/
  app/                    providers, router, theme, query client
  api/                    fetch client (JWT refresh), ApiError, XHR storage upload, types
  components/             reusable UI (layout, states, dialogs, avatar, rich-text editor/viewer,
                          attachment list)
  features/auth/          login, demo accounts, auth context, route guard
  features/tickets/       list, filters, create dialog, detail, action panel, activity
  features/notifications/ notifications bell
```
