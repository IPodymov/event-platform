import pytest
from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError

from apps.accounts.models import User
from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db


def test_auth_user_model_is_custom_user() -> None:
    assert get_user_model() is User
    assert User.USERNAME_FIELD == "email"
    assert User.REQUIRED_FIELDS == []


def test_user_has_no_username_field() -> None:
    field_names = {f.name for f in User._meta.get_fields()}

    assert "username" not in field_names


def test_create_user_normalizes_email_and_hashes_password() -> None:
    user = User.objects.create_user(email="  Player@Example.COM ", password="s3cret-pass")

    assert user.email == "player@example.com"
    assert user.check_password("s3cret-pass")
    assert user.is_active
    assert not user.is_staff
    assert not user.is_superuser


def test_create_user_without_password_sets_unusable_password() -> None:
    user = User.objects.create_user(email="nopass@example.com")

    assert not user.has_usable_password()


def test_create_user_requires_email() -> None:
    with pytest.raises(ValueError, match="email"):
        User.objects.create_user(email="", password="s3cret-pass")


def test_create_superuser_sets_admin_flags() -> None:
    admin = User.objects.create_superuser(email="root@example.com", password="s3cret-pass")

    assert admin.is_staff
    assert admin.is_superuser


@pytest.mark.parametrize("flag", ["is_staff", "is_superuser"])
def test_create_superuser_rejects_disabled_flags(flag: str) -> None:
    with pytest.raises(ValueError, match=flag):
        User.objects.create_superuser(
            email="root@example.com", password="s3cret-pass", **{flag: False}
        )


def test_email_is_unique_case_insensitively() -> None:
    UserFactory.create(email="dup@example.com")

    # Bypass the manager to make sure the database constraint itself holds.
    with pytest.raises(IntegrityError):
        User(email="DUP@example.com").save()


def test_authenticate_by_email_ignores_case() -> None:
    user = UserFactory.create(email="login@example.com")

    assert authenticate(username="LOGIN@Example.com", password=DEFAULT_PASSWORD) == user
    assert authenticate(username="login@example.com", password="wrong") is None


def test_full_clean_normalizes_email() -> None:
    user = User(email="Mixed@Example.com")
    user.set_unusable_password()

    user.full_clean()

    assert user.email == "mixed@example.com"


def test_str_is_email() -> None:
    assert str(UserFactory.build(email="a@example.com")) == "a@example.com"
