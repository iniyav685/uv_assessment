from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Role, User
from apps.organizations.models import (
    Client,
    ClientOffice,
    Department,
    Floor,
    IssueType,
    Location,
    Property,
)

PASSWORD = "pass12345!"


def make_user(username, role, **extra):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password=PASSWORD,
        role=role,
        first_name=username.split(".")[-1].title(),
        **extra,
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client():
    def _client(user):
        client = APIClient()
        token = RefreshToken.for_user(user).access_token
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    return _client


@pytest.fixture
def world(db):
    """
    Minimal organisation:
      Technical (POC tech_poc, technician tech) and IT (POC it_poc, technician it_tech)
      Locations Koramangala (FM fm) and HSR Layout (FM other_fm).
      Property "Harness" in Koramangala, with Acme (2 floors) and Globex (1 floor) offices.
    """
    technical = Department.objects.create(name="Technical", code="technical")
    it = Department.objects.create(name="IT", code="it")
    tech_poc = make_user("poc.technical", Role.DEPARTMENT_POC, department=technical)
    it_poc = make_user("poc.it", Role.DEPARTMENT_POC, department=it)
    technical.poc = tech_poc
    technical.save()
    it.poc = it_poc
    it.save()
    tech = make_user("tech.prakash", Role.TECHNICIAN, department=technical)
    it_tech = make_user("tech.kiran", Role.TECHNICIAN, department=it)

    koramangala = Location.objects.create(city="Bengaluru", area="Koramangala")
    hsr = Location.objects.create(city="Bengaluru", area="HSR Layout")
    fm = make_user("fm.chandan", Role.FACILITY_MANAGER, location=koramangala)
    other_fm = make_user("fm.neha", Role.FACILITY_MANAGER, location=hsr)
    harness = Property.objects.create(
        name="Harness Tech Park", code="Harness", location=koramangala
    )

    acme = ClientOffice.objects.create(
        client=Client.objects.create(name="Acme"), property=harness, unit="1317"
    )
    floor2 = Floor.objects.create(office=acme, level=2, label="2F")
    floor3 = Floor.objects.create(office=acme, level=3, label="3F")
    globex = ClientOffice.objects.create(
        client=Client.objects.create(name="Globex"), property=harness, unit="1402"
    )
    Floor.objects.create(office=globex, level=5, label="5F")

    return SimpleNamespace(
        technical=technical,
        it=it,
        tech_poc=tech_poc,
        it_poc=it_poc,
        tech=tech,
        it_tech=it_tech,
        fm=fm,
        other_fm=other_fm,
        acme=acme,
        globex=globex,
        floors=[floor2, floor3],
        client=make_user("client.acme", Role.CLIENT_POC, client_office=acme),
        globex_client=make_user("client.globex", Role.CLIENT_POC, client_office=globex),
        ac=IssueType.objects.create(name="AC not cooling", department=technical, is_quick=True),
        internet=IssueType.objects.create(name="Internet not working", department=it),
        admin=make_user("admin", Role.ADMIN),
    )
