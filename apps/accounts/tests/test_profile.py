from pathlib import Path
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks, Settings
from rest_framework.test import APIClient

from apps.accounts import services
from apps.accounts.exceptions import AvatarTooLargeError, InvalidAvatarError, NicknameTakenError
from apps.accounts.models import Profile
from apps.accounts.tests.factories import ProfileFactory, UserFactory
from apps.accounts.tests.images import image_upload

pytestmark = pytest.mark.django_db

PROFILE_API = "/api/v1/me/profile/"


# --- services ----------------------------------------------------------------


def test_profile_create() -> None:
    user = UserFactory.create(profile=None)

    profile = services.profile_create(user=user, nickname="s1mple")

    assert profile.user == user
    assert profile.timezone == "Europe/Moscow"


def test_profile_create_rejects_taken_nickname_ignoring_case() -> None:
    ProfileFactory.create(nickname="ZywOo")

    with pytest.raises(NicknameTakenError):
        services.profile_create(user=UserFactory.create(profile=None), nickname="zywoo")


@pytest.mark.parametrize("nickname", ["ab", "a" * 21, "with space", "кириллица", "dot.ted"])
def test_profile_create_rejects_invalid_nickname(nickname: str) -> None:
    with pytest.raises(ValidationError):
        services.profile_create(user=UserFactory.create(profile=None), nickname=nickname)


def test_profile_update_fields() -> None:
    profile = ProfileFactory.create()

    services.profile_update(
        profile=profile,
        data={"nickname": "NewNick", "country": "KZ", "timezone": "Asia/Almaty", "bio": "AWP"},
    )

    profile.refresh_from_db()
    assert (profile.nickname, profile.country.code, profile.timezone, profile.bio) == (
        "NewNick",
        "KZ",
        "Asia/Almaty",
        "AWP",
    )


def test_profile_update_allows_changing_case_of_own_nickname() -> None:
    profile = ProfileFactory.create(nickname="player")

    services.profile_update(profile=profile, data={"nickname": "Player"})

    assert Profile.objects.get(pk=profile.pk).nickname == "Player"


def test_profile_update_rejects_someone_elses_nickname() -> None:
    ProfileFactory.create(nickname="taken")

    with pytest.raises(NicknameTakenError):
        services.profile_update(profile=ProfileFactory.create(), data={"nickname": "TAKEN"})


def test_profile_update_rejects_unknown_timezone() -> None:
    with pytest.raises(ValidationError):
        services.profile_update(profile=ProfileFactory.create(), data={"timezone": "Mars/Base"})


def test_profile_update_rejects_non_editable_fields() -> None:
    with pytest.raises(ValueError, match="user"):
        services.profile_update(profile=ProfileFactory.create(), data={"user": None})


# --- avatars -----------------------------------------------------------------


def test_avatar_is_resized_and_reencoded_as_webp() -> None:
    profile = ProfileFactory.create()

    services.profile_update(profile=profile, data={}, avatar=image_upload(size=(2000, 1000)))

    assert profile.avatar.name.startswith("avatars/")
    assert profile.avatar.name.endswith(".webp")
    with Image.open(profile.avatar.path) as stored:
        assert stored.format == "WEBP"
        assert stored.size == (512, 256)


@pytest.mark.parametrize("fmt", ["JPEG", "WEBP"])
def test_avatar_accepts_jpeg_and_webp(fmt: str) -> None:
    profile = ProfileFactory.create()

    services.profile_update(profile=profile, data={}, avatar=image_upload(fmt=fmt))

    assert profile.avatar.name.endswith(".webp")


@pytest.mark.parametrize(
    "upload",
    [
        image_upload(fmt="GIF", name="a.gif"),
        SimpleUploadedFile("a.png", b"<?php echo 'not an image'; ?>", content_type="image/png"),
    ],
    ids=["gif", "not-an-image"],
)
def test_avatar_rejects_other_formats(upload: SimpleUploadedFile, settings: Settings) -> None:
    profile = ProfileFactory.create()

    with pytest.raises(InvalidAvatarError):
        services.profile_update(profile=profile, data={}, avatar=upload)

    assert not any(Path(settings.MEDIA_ROOT).rglob("*.webp"))


def test_avatar_rejects_too_many_bytes(settings: Settings) -> None:
    settings.AVATAR_MAX_BYTES = 100

    with pytest.raises(AvatarTooLargeError):
        services.profile_update(profile=ProfileFactory.create(), data={}, avatar=image_upload())


def test_avatar_rejects_too_many_pixels_before_decoding(settings: Settings) -> None:
    settings.AVATAR_MAX_PIXELS = 100

    with pytest.raises(AvatarTooLargeError):
        services.profile_update(profile=ProfileFactory.create(), data={}, avatar=image_upload())


def test_replacing_avatar_deletes_old_file_after_commit(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    profile = ProfileFactory.create()
    services.profile_update(profile=profile, data={}, avatar=image_upload())
    old_path = Path(profile.avatar.path)

    with django_capture_on_commit_callbacks(execute=True):
        services.profile_update(profile=profile, data={}, avatar=image_upload())

    assert not old_path.exists()
    assert Path(profile.avatar.path).exists()


def test_failed_update_removes_new_avatar_file(settings: Settings) -> None:
    ProfileFactory.create(nickname="taken")
    profile = ProfileFactory.create()

    with pytest.raises(NicknameTakenError):
        services.profile_update(profile=profile, data={"nickname": "taken"}, avatar=image_upload())

    assert not any(Path(settings.MEDIA_ROOT).rglob("*.webp"))


# --- profile page ------------------------------------------------------------


def test_profile_page_requires_login(client: Client) -> None:
    response = client.get(reverse("accounts:profile_edit"))

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("account_login"))


def test_profile_page_updates_profile(client: Client) -> None:
    user = UserFactory.create()
    client.force_login(user)

    response = client.post(
        reverse("accounts:profile_edit"),
        {
            "nickname": "edited",
            "country": "RU",
            "timezone": "Asia/Yekaterinburg",
            "bio": "",
            "avatar": image_upload(),
        },
    )

    assert response.status_code == 302
    user.profile.refresh_from_db()
    assert user.profile.nickname == "edited"
    assert user.profile.avatar.name.endswith(".webp")


def test_profile_page_shows_taken_nickname_error(client: Client) -> None:
    ProfileFactory.create(nickname="taken")
    user = UserFactory.create()
    client.force_login(user)

    response = client.post(
        reverse("accounts:profile_edit"),
        {"nickname": "Taken", "country": "", "timezone": "UTC", "bio": ""},
    )

    assert response.status_code == 200
    assert response.context["form"].errors["nickname"]


# --- API ---------------------------------------------------------------------


def test_api_requires_authentication(api_client: APIClient) -> None:
    assert api_client.get(PROFILE_API).status_code == 403


def test_api_get_own_profile(api_client: APIClient) -> None:
    user = UserFactory.create(email="me@example.com", profile__nickname="me_myself")
    api_client.force_authenticate(user)

    data = api_client.get(PROFILE_API).json()

    assert data["nickname"] == "me_myself"
    assert data["email"] == "me@example.com"
    assert data["timezone"] == "Europe/Moscow"


def test_api_patch_json(api_client: APIClient) -> None:
    user = UserFactory.create()
    api_client.force_authenticate(user)

    response = api_client.patch(PROFILE_API, {"country": "BY", "bio": "IGL"}, format="json")

    assert response.status_code == 200
    assert response.json()["country"] == "BY"


def test_api_patch_avatar_multipart(api_client: APIClient) -> None:
    user = UserFactory.create()
    api_client.force_authenticate(user)

    response = api_client.patch(PROFILE_API, {"avatar": image_upload()}, format="multipart")

    assert response.status_code == 200
    assert response.json()["avatar"].endswith(".webp")


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"nickname": "TAKEN"}, "nickname"),
        ({"nickname": "a b"}, "nickname"),
        ({"timezone": "Mars/Base"}, "timezone"),
        ({"country": "XX"}, "country"),
    ],
)
def test_api_patch_validation_errors(
    api_client: APIClient, payload: dict[str, Any], field: str
) -> None:
    ProfileFactory.create(nickname="taken")
    api_client.force_authenticate(UserFactory.create())

    response = api_client.patch(PROFILE_API, payload, format="json")

    assert response.status_code == 400
    assert field in response.json()


def test_api_email_is_read_only(api_client: APIClient) -> None:
    user = UserFactory.create(email="keep@example.com")
    api_client.force_authenticate(user)

    api_client.patch(PROFILE_API, {"email": "other@example.com"}, format="json")

    user.refresh_from_db()
    assert user.email == "keep@example.com"


# --- time zone ---------------------------------------------------------------


def test_middleware_activates_profile_timezone(client: Client) -> None:
    user = UserFactory.create(profile__timezone="Asia/Vladivostok")
    client.force_login(user)

    response = client.get(reverse("home"))

    assert response.wsgi_request is not None
    assert str(timezone.get_current_timezone()) == "Asia/Vladivostok"


def test_middleware_uses_utc_for_anonymous(client: Client) -> None:
    client.get(reverse("home"))

    assert str(timezone.get_current_timezone()) == "UTC"
