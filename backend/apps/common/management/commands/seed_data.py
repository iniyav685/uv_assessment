"""
Reproducible sample data:
`python manage.py seed_data [--reset] [--tickets N] [--extra-technicians-per-dept N] [--extra-clients N]`.

Reference data and users are upserted (safe to re-run). Tickets are generated
with a fixed random seed through the real service layer, so every seeded ticket
has a consistent activity trail, then back-dated to spread across ~6 weeks.
"""

import random
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.common.richtext import text_to_html
from apps.notifications.dispatch import suppress_notifications
from apps.notifications.models import Notification
from apps.organizations.models import (
    Client,
    ClientOffice,
    Department,
    Floor,
    IssueType,
    Location,
    Property,
)
from apps.tickets import services
from apps.tickets.models import AssessmentOutcome, Ticket, TicketActivity, TicketComment

DEPARTMENTS = [
    ("technical", "Technical"),
    ("it", "IT"),
    ("housekeeping", "Housekeeping"),
    ("electrical", "Electrical"),
]

LOCATIONS = {
    "kor": ("Bengaluru", "Koramangala"),
    "hsr": ("Bengaluru", "HSR Layout"),
    "wf": ("Bengaluru", "Whitefield"),
}

DEPT_TITLES = {
    "technical": ("Technical Manager", "Technician"),
    "it": ("IT Manager", "IT Technician"),
    "housekeeping": ("Housekeeping Manager", "Housekeeping Staff"),
    "electrical": ("Electrical Supervisor", "Electrician"),
}

# username, first, last, role, department code, location key
# Facility Managers: exactly one per location — new tickets auto-link to them.
# Department POCs: one per department (Department.poc) — new tickets auto-assign to them.
INTERNAL_USERS = [
    ("admin", "Ada", "Admin", Role.ADMIN, None, None),
    ("fm.chandan", "Chandan", "S", Role.FACILITY_MANAGER, None, "kor"),
    ("fm.neha", "Neha", "Gupta", Role.FACILITY_MANAGER, None, "hsr"),
    ("fm.rohit", "Rohit", "Bansal", Role.FACILITY_MANAGER, None, "wf"),
    ("poc.technical", "Dhananjaya", "Murthy", Role.DEPARTMENT_POC, "technical", None),
    ("poc.it", "Abdul", "Rahman", Role.DEPARTMENT_POC, "it", None),
    ("poc.housekeeping", "Lakshmi", "Iyer", Role.DEPARTMENT_POC, "housekeeping", None),
    ("poc.electrical", "Vinod", "Shetty", Role.DEPARTMENT_POC, "electrical", None),
    ("tech.prakash", "Prakash", "Kumar", Role.TECHNICIAN, "technical", None),
    ("tech.ravi", "Ravi", "Teja", Role.TECHNICIAN, "technical", None),
    ("tech.kiran", "Kiran", "Rao", Role.TECHNICIAN, "it", None),
    ("tech.meera", "Meera", "Nair", Role.TECHNICIAN, "it", None),
    ("tech.suresh", "Suresh", "Babu", Role.TECHNICIAN, "housekeeping", None),
    ("tech.arjun", "Arjun", "Das", Role.TECHNICIAN, "electrical", None),
]


def title_for(role, dept):
    if role == Role.ADMIN:
        return "Administrator"
    if role == Role.FACILITY_MANAGER:
        return "Facility Manager"
    manager, staff = DEPT_TITLES[dept]
    return manager if role == Role.DEPARTMENT_POC else staff


# code, name, location key
PROPERTIES = [
    ("Harness", "Harness Tech Park", "kor"),
    ("HSR", "HSR Business Centre", "hsr"),
    ("WF", "Whitefield Towers", "wf"),
]

# client, property code, unit, floors [(level, label)]
OFFICES = [
    ("Acme Corp", "Harness", "1317", [(2, "2F"), (3, "3F")]),
    ("Globex", "HSR", "1317", [(1, "1F"), (2, "2F"), (3, "3F")]),
    ("Initech", "WF", "204", [(4, "4F")]),
    ("Umbrella Health", "Harness", "1402", [(5, "5F")]),
    ("Stark Industries", "HSR", "220", [(0, "GF"), (1, "1F")]),
]

CLIENT_POCS = [
    ("client.acme", "Chaitanya", "M", "Acme Corp"),
    ("client.globex", "Priya", "Sharma", "Globex"),
    ("client.initech", "Rahul", "Verma", "Initech"),
    ("client.umbrella", "Ananya", "Kapoor", "Umbrella Health"),
    ("client.stark", "Tony", "Pereira", "Stark Industries"),
]

# Name pool for generated (--extra-technicians-per-dept / --extra-clients) users,
# consumed in order so results stay reproducible across runs.
EXTRA_FIRST_NAMES = [
    "Arjun", "Vikram", "Sanjay", "Deepa", "Kavya", "Rohan", "Meena", "Farah",
    "Naveen", "Divya", "Karthik", "Pooja", "Aditya", "Sneha", "Rajesh", "Anita",
    "Manoj", "Swati", "Harish", "Nisha",
]
EXTRA_LAST_NAMES = [
    "Rao", "Nair", "Menon", "Iyer", "Gupta", "Sharma", "Verma", "Reddy",
    "Naidu", "Pillai", "Chandra", "Bose", "Kulkarni", "Desai", "Joshi", "Patil",
]

EXTRA_CLIENT_NAMES = [
    "Nimbus Systems", "Solstice Labs", "Vertex Analytics", "Bluepeak Retail",
    "Crimson Foods", "Meridian Health", "Alder Finance", "Pinegrove Media",
    "Sundial Logistics", "Wavecrest Tech",
]

EXTRA_CLIENT_FLOOR_OPTIONS = [
    [(1, "1F")],
    [(2, "2F")],
    [(1, "1F"), (2, "2F")],
    [(3, "3F")],
]


def extra_name_pool():
    for last in EXTRA_LAST_NAMES:
        for first in EXTRA_FIRST_NAMES:
            yield first, last

# name, department code, quick issue
ISSUES = [
    ("AC not cooling", "technical", True),
    ("Lift servicing", "technical", False),
    ("Water leakage", "technical", False),
    ("Internet not working", "it", True),
    ("Wi-Fi slow", "it", False),
    ("Printer not working", "it", False),
    ("Pantry not cleaned", "housekeeping", True),
    ("Washroom needs cleaning", "housekeeping", False),
    ("Lights flickering", "electrical", True),
    ("Power outage", "electrical", False),
]

DESCRIPTIONS = {
    "AC not cooling": "The air conditioning units have stopped cooling effectively since this "
    "morning. The units appear to be running but producing warm air.",
    "Lift servicing": "Lift is making a grinding noise and stops unevenly at floors.",
    "Water leakage": "Water is dripping from the ceiling near the meeting rooms.",
    "Internet not working": "The wired network is down across the office. Wi-Fi is unaffected.",
    "Wi-Fi slow": "Wi-Fi speed drops sharply during the afternoon; video calls keep freezing.",
    "Printer not working": "The shared printer shows a paper jam error even when empty.",
    "Pantry not cleaned": "The pantry was not cleaned this morning and bins are overflowing.",
    "Washroom needs cleaning": "Washrooms need attention; soap dispensers are also empty.",
    "Lights flickering": "Ceiling lights near the workstations flicker continuously.",
    "Power outage": "Partial power outage — half the workstations have no power.",
}

# Free-text titles as a user would write them; {floors} is filled with the chosen floors.
TITLES = {
    "AC not cooling": ["AC blowing warm air on {floors}", "Cabin too hot — AC not cooling"],
    "Lift servicing": ["Lift making grinding noise", "Lift stops unevenly at floors"],
    "Water leakage": ["Ceiling leak near meeting rooms", "Water dripping on {floors}"],
    "Internet not working": ["Wired internet down on {floors}", "No network at workstations"],
    "Wi-Fi slow": ["Wi-Fi very slow in the afternoon", "Video calls freezing on Wi-Fi"],
    "Printer not working": ["Printer shows paper jam", "Shared printer offline"],
    "Pantry not cleaned": ["Pantry not cleaned this morning", "Pantry bins overflowing"],
    "Washroom needs cleaning": ["Washrooms need cleaning", "Soap dispensers empty"],
    "Lights flickering": ["Lights flickering near workstations", "Tube lights flicker on {floors}"],
    "Power outage": ["Half the workstations have no power", "Power outage on {floors}"],
}

COMMENTS = [
    "Any update on this?",
    "Technician visited, parts have been ordered.",
    "Issue is still happening intermittently.",
    "Please prioritise, this is affecting the whole team.",
    "Checked on site, will follow up tomorrow.",
]


def upsert_user(username, first, last, role, title, **extra):
    user, created = User.objects.update_or_create(
        username=username,
        defaults={
            "email": f"{username}@example.com",
            "first_name": first,
            "last_name": last,
            "role": role,
            "title": title,
            "is_staff": role == Role.ADMIN,
            "is_superuser": role == Role.ADMIN,
            **extra,
        },
    )
    if created:
        user.set_password(settings.DEMO_PASSWORD)
        user.save(update_fields=["password"])
    return user


class Command(BaseCommand):
    help = "Load demo organisations, users and tickets."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing tickets first.")
        parser.add_argument("--tickets", type=int, default=64)
        parser.add_argument(
            "--extra-technicians-per-dept",
            type=int,
            default=0,
            help="Generated technicians to add per department, beyond the named roster.",
        )
        parser.add_argument(
            "--extra-clients",
            type=int,
            default=0,
            help="Generated client companies (with an office and a POC) to add, beyond the named roster.",
        )

    @transaction.atomic
    def handle(
        self,
        *args,
        reset=False,
        tickets=64,
        extra_technicians_per_dept=0,
        extra_clients=0,
        **options,
    ):
        self.seed_reference_data(extra_technicians_per_dept, extra_clients)
        if reset:
            Notification.objects.all().delete()
            TicketActivity.objects.all().delete()
            Ticket.objects.all().delete()
        if Ticket.objects.exists():
            self.stdout.write("Tickets already present — skipping (use --reset to regenerate).")
        else:
            with suppress_notifications():
                self.seed_tickets(tickets)
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: {User.objects.count()} users, {Ticket.objects.count()} tickets. "
                f"Demo password: {settings.DEMO_PASSWORD}"
            )
        )

    # --- reference data ---------------------------------------------------

    def seed_reference_data(self, extra_technicians_per_dept=0, extra_clients=0):
        names = extra_name_pool()
        depts = {
            code: Department.objects.update_or_create(code=code, defaults={"name": name})[0]
            for code, name in DEPARTMENTS
        }
        locations = {
            key: Location.objects.get_or_create(city=city, area=area)[0]
            for key, (city, area) in LOCATIONS.items()
        }
        users = {}
        for username, first, last, role, dept, loc in INTERNAL_USERS:
            users[username] = upsert_user(
                username,
                first,
                last,
                role,
                title_for(role, dept),
                department=depts.get(dept),
                location=locations.get(loc),
            )

        for dept_code, username in [
            ("technical", "poc.technical"),
            ("it", "poc.it"),
            ("housekeeping", "poc.housekeeping"),
            ("electrical", "poc.electrical"),
        ]:
            Department.objects.filter(pk=depts[dept_code].pk).update(poc=users[username])

        if extra_technicians_per_dept:
            for dept_code, _ in DEPARTMENTS:
                title = DEPT_TITLES[dept_code][1]
                for i in range(extra_technicians_per_dept):
                    first, last = next(names)
                    username = f"tech.{dept_code}.{i + 1}"
                    users[username] = upsert_user(
                        username, first, last, Role.TECHNICIAN, title, department=depts[dept_code]
                    )

        props = {
            code: Property.objects.update_or_create(
                code=code, defaults={"name": name, "location": locations[loc]}
            )[0]
            for code, name, loc in PROPERTIES
        }
        offices = {}
        for client_name, prop_code, unit, floors in OFFICES:
            client, _ = Client.objects.get_or_create(name=client_name)
            office, _ = ClientOffice.objects.update_or_create(
                property=props[prop_code], unit=unit, defaults={"client": client}
            )
            for level, label in floors:
                Floor.objects.update_or_create(
                    office=office, level=level, defaults={"label": label}
                )
            offices[client_name] = office

        for username, first, last, client_name in CLIENT_POCS:
            upsert_user(
                username,
                first,
                last,
                Role.CLIENT_POC,
                "Client POC",
                client_office=offices[client_name],
            )

        if extra_clients:
            prop_codes = [code for code, _, _ in PROPERTIES]
            for i in range(extra_clients):
                base_name = EXTRA_CLIENT_NAMES[i % len(EXTRA_CLIENT_NAMES)]
                cycle = i // len(EXTRA_CLIENT_NAMES)
                client_name = base_name if cycle == 0 else f"{base_name} {cycle + 1}"
                prop_code = prop_codes[i % len(prop_codes)]
                unit = str(300 + i)
                floors = EXTRA_CLIENT_FLOOR_OPTIONS[i % len(EXTRA_CLIENT_FLOOR_OPTIONS)]

                client, _ = Client.objects.get_or_create(name=client_name)
                office, _ = ClientOffice.objects.update_or_create(
                    property=props[prop_code], unit=unit, defaults={"client": client}
                )
                for level, label in floors:
                    Floor.objects.update_or_create(
                        office=office, level=level, defaults={"label": label}
                    )

                first, last = next(names)
                upsert_user(
                    f"client.extra{i + 1}",
                    first,
                    last,
                    Role.CLIENT_POC,
                    "Client POC",
                    client_office=office,
                )

        for name, dept_code, quick in ISSUES:
            IssueType.objects.update_or_create(
                name=name, defaults={"department": depts[dept_code], "is_quick": quick}
            )

    # --- tickets ----------------------------------------------------------

    def seed_tickets(self, count):
        rng = random.Random(42)
        now = timezone.now()
        client_pocs = list(
            User.objects.filter(role=Role.CLIENT_POC).select_related("client_office__property")
        )
        fm_by_location = {u.location_id: u for u in User.objects.filter(role=Role.FACILITY_MANAGER)}
        issues = list(IssueType.objects.select_related("department"))
        departments = list(Department.objects.all())
        technicians = {}
        for t in User.objects.filter(role=Role.TECHNICIAN):
            technicians.setdefault(t.department_id, []).append(t)

        # Weighted end states for a realistic mix across both tabs.
        stages = (
            ["new"] * 30
            + ["assigned"] * 20
            + ["review"] * 12
            + ["blocked"] * 8
            + ["closed"] * 15
            + ["resolved"] * 10
            + ["moved"] * 5
        )

        for i in range(count):
            poc_client = rng.choice(client_pocs)
            office = poc_client.client_office
            # ~30% raised by the facility manager on the client's behalf.
            creator = poc_client
            location_fm = fm_by_location.get(office.property.location_id)
            if rng.random() < 0.3 and location_fm:
                creator = location_fm
            issue = rng.choice(issues)
            office_floors = list(office.floors.all())
            floors = rng.sample(office_floors, rng.randint(1, len(office_floors)))
            if i == count - 1:
                # The newest ticket mirrors the wireframe's walkthrough example.
                creator = next(u for u in client_pocs if u.username == "client.acme")
                office = creator.client_office
                issue = next(x for x in issues if x.name == "AC not cooling")
                floors = list(office.floors.all())

            tags = [issue]
            if i != count - 1 and rng.random() < 0.25:
                tags.append(rng.choice([x for x in issues if x.id != issue.id]))
            floor_text = ", ".join(f.label for f in floors)
            title = (
                "AC units on 2F and 3F blowing warm air"
                if i == count - 1
                else rng.choice(TITLES[issue.name]).format(floors=floor_text)
            )
            ticket = services.create_ticket(
                user=creator,
                client_office=office,
                title=title,
                issue_types=tags,
                floors=floors,
                description=text_to_html(DESCRIPTIONS[issue.name]),
            )
            # Keep the newest ticket as the wireframe's walkthrough example.
            stage = "new" if i == count - 1 else rng.choice(stages)
            self.advance(ticket, stage, rng, technicians, departments, poc_client)
            for _ in range(rng.choice([0, 0, 1, 2])):
                if Ticket.objects.get(pk=ticket.pk).is_open:
                    services.add_comment(
                        user=poc_client,
                        ticket_id=ticket.pk,
                        body_html=f"<p>{rng.choice(COMMENTS)}</p>",
                    )

            age = (
                timedelta(hours=1)
                if i == count - 1
                else timedelta(days=rng.uniform(0.5, 45) * (count - i) / count)
            )
            self.backdate(ticket.pk, now - age, rng)

    def advance(self, ticket, stage, rng, technicians, departments, poc_client):
        if stage == "new" or not ticket.facility_manager:
            return  # stays in Pending Facility Manager Review

        # The FM forwards it to the tag-suggested department before anything else can happen.
        services.forward_to_department(
            user=ticket.facility_manager, ticket_id=ticket.pk, department=ticket.department
        )
        ticket.refresh_from_db()
        poc = ticket.department_poc
        if stage == "moved":
            target = rng.choice([d for d in departments if d.id != ticket.department_id])
            services.change_department(
                user=poc,
                ticket_id=ticket.pk,
                department=target,
                note="This belongs to another team — forwarding.",
            )
            return
        tech = rng.choice(technicians[ticket.department_id])
        services.assign_worker(user=poc, ticket_id=ticket.pk, technician=tech)
        if stage == "assigned":
            return
        if stage == "resolved":
            # Only a Client POC of the ticket's client can mark it resolved — not
            # necessarily whoever created it (e.g. an FM raising it on their behalf).
            services.mark_resolved(user=poc_client, ticket_id=ticket.pk)
            return
        outcome = (
            AssessmentOutcome.FULLY_RESOLVED
            if stage in ("review", "closed")
            else rng.choice(
                [AssessmentOutcome.PARTIALLY_RESOLVED, AssessmentOutcome.NEEDS_REASSIGNMENT]
            )
        )
        comment = (
            ""
            if outcome == AssessmentOutcome.FULLY_RESOLVED
            else (
                "Fixed my part; the rest needs another team."
                if outcome == AssessmentOutcome.PARTIALLY_RESOLVED
                else "This is outside my scope."
            )
        )
        services.submit_assessment(user=tech, ticket_id=ticket.pk, outcome=outcome, comment=comment)
        if stage == "closed":
            services.close_ticket(user=poc, ticket_id=ticket.pk, note="Verified with the client.")

    def backdate(self, ticket_id, created_at, rng):
        now = timezone.now()
        moment = created_at
        activities = list(TicketActivity.objects.filter(ticket_id=ticket_id).order_by("id"))
        # Spread follow-up events over the time since creation, never into the future.
        step_cap = (now - created_at) / max(len(activities), 1)
        for index, activity in enumerate(activities):
            if index > 1:  # "created" and "auto-assigned" share the creation time
                moment += min(timedelta(minutes=rng.randint(20, 60 * 20)), step_cap)
            TicketActivity.objects.filter(pk=activity.pk).update(created_at=moment)
            if activity.comment_id:
                TicketComment.objects.filter(pk=activity.comment_id).update(created_at=moment)
        ticket = Ticket.objects.get(pk=ticket_id)
        Ticket.objects.filter(pk=ticket_id).update(
            created_at=created_at,
            updated_at=moment,
            closed_at=moment if ticket.closed_at else None,
        )
