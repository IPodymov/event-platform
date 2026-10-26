import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_changelist_renders(admin_client: Client) -> None:
    UserFactory.create(email="listed@example.com")

    response = admin_client.get(reverse("admin:accounts_user_changelist"), {"q": "listed"})

    assert response.status_code == 200
    assert b"listed@example.com" in response.content


def test_change_page_renders(admin_client: Client) -> None:
    user = UserFactory.create()

    response = admin_client.get(reverse("admin:accounts_user_change", args=[user.pk]))

    assert response.status_code == 200


def test_add_user_by_email(admin_client: Client) -> None:
    response = admin_client.post(
        reverse("admin:accounts_user_add"),
        {
            "email": "New.Player@Example.com",
            "usable_password": "true",
            "password1": "Very-strong-pass-42",
            "password2": "Very-strong-pass-42",
        },
    )

    assert response.status_code == 302
    user = User.objects.get(email="new.player@example.com")
    assert user.check_password("Very-strong-pass-42")
