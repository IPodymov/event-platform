from typing import Any

import pytest
from allauth.account.models import EmailAddress
from django.core import mail
from django.test import Client

from apps.accounts.models import User
from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory
from apps.accounts.tests.mail import last_email_key

pytestmark = pytest.mark.django_db

API = "/api/auth/browser/v1"
PASSWORD = "Another-strong-pass-77"


def post(client: Client, path: str, data: dict[str, Any]) -> Any:
    return client.post(f"{API}{path}", data, content_type="application/json")


def pending_flows(response: Any) -> set[str]:
    return {f["id"] for f in response.json()["data"]["flows"] if f.get("is_pending")}


def test_signup_requires_email_verification(client: Client) -> None:
    response = post(
        client,
        "/auth/signup",
        {"email": "Api@Example.com", "nickname": "api_user", "password": PASSWORD},
    )

    assert response.status_code == 401
    assert pending_flows(response) == {"verify_email"}
    assert User.objects.get(email="api@example.com").profile.nickname == "api_user"
    assert len(mail.outbox) == 1


def test_verify_email_authenticates(client: Client) -> None:
    post(
        client,
        "/auth/signup",
        {"email": "verify@example.com", "nickname": "verifier", "password": PASSWORD},
    )

    response = post(client, "/auth/email/verify", {"key": last_email_key("/confirm-email/")})

    assert response.status_code == 200
    assert response.json()["meta"]["is_authenticated"] is True
    assert EmailAddress.objects.get(email="verify@example.com").verified


def test_login_and_logout(client: Client) -> None:
    user = UserFactory.create(email="session@example.com")
    EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)

    response = post(
        client, "/auth/login", {"email": "SESSION@example.com", "password": DEFAULT_PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["data"]["user"]["email"] == "session@example.com"
    assert client.get(f"{API}/auth/session").status_code == 200

    assert client.delete(f"{API}/auth/session").status_code == 401
    assert client.get(f"{API}/auth/session").status_code == 401


def test_login_with_wrong_password_fails(client: Client) -> None:
    UserFactory.create(email="wrong@example.com")

    response = post(client, "/auth/login", {"email": "wrong@example.com", "password": "nope"})

    assert response.status_code == 400


def test_password_reset_request_sends_email(client: Client) -> None:
    user = UserFactory.create(email="forgot@example.com")
    EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)

    response = post(client, "/auth/password/request", {"email": "forgot@example.com"})

    assert response.status_code == 200
    assert mail.outbox[-1].to == ["forgot@example.com"]


def test_openapi_specification_is_served(client: Client) -> None:
    response = client.get("/api/auth/openapi.json")

    assert response.status_code == 200
    assert "/auth/login" in "".join(response.json()["paths"])


def test_signup_requires_nickname(client: Client) -> None:
    response = post(client, "/auth/signup", {"email": "nonick@example.com", "password": PASSWORD})

    assert response.status_code == 400
    assert {e["param"] for e in response.json()["errors"]} == {"nickname"}
    assert not User.objects.filter(email="nonick@example.com").exists()
