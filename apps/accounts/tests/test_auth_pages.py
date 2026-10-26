from typing import Any

import pytest
from allauth.account.models import EmailAddress
from django.core import mail
from django.test import Client
from django.urls import reverse
from django.utils import translation

from apps.accounts.models import User
from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory
from apps.accounts.tests.mail import last_email_link

pytestmark = pytest.mark.django_db

NEW_PASSWORD = "Another-strong-pass-77"


def verified_user(email: str = "verified@example.com") -> User:
    user = UserFactory.create(email=email)
    EmailAddress.objects.create(user=user, email=email, primary=True, verified=True)
    return user


def is_authenticated(client: Client) -> bool:
    return "_auth_user_id" in client.session


def signup(client: Client, email: str, nickname: str = "newbie") -> Any:
    response = client.post(
        reverse("account_signup"),
        {
            "email": email,
            "nickname": nickname,
            "password1": NEW_PASSWORD,
            "password2": NEW_PASSWORD,
        },
    )
    assert response.status_code == 302, response.context["form"].errors
    return response


def test_signup_creates_unverified_user_and_sends_confirmation(client: Client) -> None:
    signup(client, "New.Player@Example.com")

    user = User.objects.get(email="new.player@example.com")
    assert user.check_password(NEW_PASSWORD)
    assert user.profile.nickname == "newbie"
    assert not EmailAddress.objects.get(user=user).verified
    assert not is_authenticated(client)
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["new.player@example.com"]


def test_unverified_user_cannot_log_in(client: Client) -> None:
    signup(client, "pending@example.com")
    client.logout()

    response = client.post(
        reverse("account_login"), {"login": "pending@example.com", "password": NEW_PASSWORD}
    )

    assert response.status_code == 302
    assert response["Location"] == reverse("account_email_verification_sent")
    assert not is_authenticated(client)


def test_email_confirmation_verifies_and_logs_in(client: Client) -> None:
    signup(client, "confirm@example.com")

    response = client.post(last_email_link("/accounts/confirm-email/"))

    assert response.status_code == 302
    assert EmailAddress.objects.get(email="confirm@example.com").verified
    assert is_authenticated(client)


def test_login_is_case_insensitive(client: Client) -> None:
    verified_user("login@example.com")

    response = client.post(
        reverse("account_login"), {"login": "LOGIN@Example.com", "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 302
    assert response["Location"] == reverse("home")
    assert is_authenticated(client)


def test_signup_with_taken_email_creates_no_account(client: Client) -> None:
    verified_user("taken@example.com")

    signup(client, "Taken@Example.com")

    assert User.objects.count() == 1
    # Enumeration prevention: the owner is notified instead of an error being shown.
    assert mail.outbox[-1].to == ["taken@example.com"]


def test_password_reset(client: Client) -> None:
    user = verified_user("reset@example.com")

    client.post(reverse("account_reset_password"), {"email": "reset@example.com"})
    response = client.get(last_email_link("/accounts/password/reset/key/"))
    assert response.status_code == 302
    response = client.post(
        response["Location"], {"password1": NEW_PASSWORD, "password2": NEW_PASSWORD}
    )

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)


def test_failed_logins_are_rate_limited(client: Client) -> None:
    verified_user("target@example.com")
    url = reverse("account_login")
    for _ in range(5):
        client.post(url, {"login": "target@example.com", "password": "wrong-password"})

    response = client.post(url, {"login": "target@example.com", "password": DEFAULT_PASSWORD})

    # The correct password is refused: allauth reports the lockout as a form error.
    assert response.status_code == 200
    assert response.context["form"].non_field_errors()
    assert not is_authenticated(client)


def test_home_page_renders(client: Client) -> None:
    assert client.get(reverse("home")).status_code == 200


@pytest.mark.parametrize(
    ("nickname", "error"),
    [("", "required"), ("x", "3 to 20"), ("имя_игрока", "Latin"), ("TAKEN", "taken")],
)
def test_signup_rejects_bad_nickname(client: Client, nickname: str, error: str) -> None:
    UserFactory.create(profile__nickname="taken")

    with translation.override("en"):
        response = client.post(
            reverse("account_signup"),
            {
                "email": "x@example.com",
                "nickname": nickname,
                "password1": NEW_PASSWORD,
                "password2": NEW_PASSWORD,
            },
            HTTP_ACCEPT_LANGUAGE="en",
        )
        # Error messages are lazy: render them while English is active.
        errors = " ".join(response.context["form"].errors["nickname"])

    assert response.status_code == 200
    assert error in errors
    assert not User.objects.filter(email="x@example.com").exists()
