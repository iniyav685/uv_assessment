import pytest
from django.db import IntegrityError
from django.urls import reverse

from apps.accounts.models import Role, User

pytestmark = pytest.mark.django_db


def test_login_returns_tokens(api_client, world):
    res = api_client.post(
        reverse("auth-login"), {"username": "client.acme", "password": "pass12345!"}
    )
    assert res.status_code == 200
    assert {"access", "refresh"} <= res.json().keys()


def test_login_with_bad_password_uses_error_envelope(api_client, world):
    res = api_client.post(reverse("auth-login"), {"username": "client.acme", "password": "nope"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "no_active_account"


def test_protected_endpoints_require_authentication(api_client):
    for url in (reverse("auth-me"), reverse("ticket-list"), reverse("lookups")):
        res = api_client.get(url)
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "not_authenticated"


def test_me_returns_role_and_capabilities(auth_client, world):
    body = auth_client(world.tech).get(reverse("auth-me")).json()
    assert body["role"] == "technician"
    assert body["can_create_ticket"] is False


def test_client_poc_must_belong_to_an_office(db):
    with pytest.raises(IntegrityError):
        User.objects.create_user(username="x", email="x@example.com", role=Role.CLIENT_POC)
