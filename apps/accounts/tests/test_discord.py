from collections.abc import Callable, Iterator
from typing import Any
from unittest import mock
from urllib.parse import parse_qs, urlparse

import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.selectors import get_discord_id
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

DISCORD_ID = "80351110224678912"
OTHER_DISCORD_ID = "80351110224678913"

DiscordRoundTrip = Callable[..., Any]


def fake_http_response(payload: dict[str, Any]) -> mock.Mock:
    response = mock.Mock(status_code=200, headers={"content-type": "application/json"})
    response.json.return_value = payload
    return response


@pytest.fixture
def discord(settings: Any) -> Iterator[DiscordRoundTrip]:
    """Run the OAuth2 round trip with Discord's token and profile endpoints faked."""
    settings.SOCIALACCOUNT_PROVIDERS["discord"]["APP"] = {"client_id": "id", "secret": "s"}
    profile: dict[str, Any] = {}
    session = mock.MagicMock()
    session.__enter__.return_value = session
    session.request.return_value = fake_http_response(
        {"access_token": "token", "token_type": "Bearer", "expires_in": 604800}
    )
    session.get.side_effect = lambda *args, **kwargs: fake_http_response(profile)

    def round_trip(client: Client, discord_id: str, process: str = "login") -> Any:
        profile.clear()
        profile.update(
            {"id": discord_id, "username": "zywoo", "email": "z@x.com", "verified": True}
        )
        response = client.post(reverse("discord_login"), {"process": process})
        assert response.status_code == 302
        authorize = urlparse(response["Location"])
        assert authorize.netloc == "discord.com"
        query = parse_qs(authorize.query)
        assert query["scope"] == ["identify"]
        return client.get(
            reverse("discord_callback"), {"code": "auth-code", "state": query["state"][0]}
        )

    with mock.patch(
        "apps.accounts.adapters.SocialAccountAdapter.get_requests_session", return_value=session
    ):
        yield round_trip


def verified_user(email: str = "player@example.com") -> User:
    user = UserFactory.create(email=email)
    EmailAddress.objects.create(user=user, email=email, primary=True, verified=True)
    return user


def logged_in_user_id(client: Client) -> int | None:
    value = client.session.get("_auth_user_id")
    return int(value) if value else None


def test_connect_links_discord_without_touching_emails(
    client: Client, discord: DiscordRoundTrip
) -> None:
    user = verified_user()
    client.force_login(user)

    response = discord(client, DISCORD_ID, process="connect")

    assert response.status_code == 302
    assert get_discord_id(user) == DISCORD_ID
    assert list(EmailAddress.objects.values_list("email", flat=True)) == ["player@example.com"]


def test_login_with_linked_discord(client: Client, discord: DiscordRoundTrip) -> None:
    user = verified_user()
    SocialAccount.objects.create(user=user, provider="discord", uid=DISCORD_ID)

    discord(client, DISCORD_ID)

    assert logged_in_user_id(client) == user.pk


def test_unlinked_discord_cannot_sign_up(client: Client, discord: DiscordRoundTrip) -> None:
    response = discord(client, DISCORD_ID)

    assert response["Location"] == reverse("account_login")
    assert logged_in_user_id(client) is None
    assert not User.objects.exists()


def test_second_discord_account_is_refused(client: Client, discord: DiscordRoundTrip) -> None:
    user = verified_user()
    SocialAccount.objects.create(user=user, provider="discord", uid=DISCORD_ID)
    client.force_login(user)

    response = discord(client, OTHER_DISCORD_ID, process="connect")

    assert response["Location"] == reverse("socialaccount_connections")
    assert get_discord_id(user) == DISCORD_ID


def test_steam_and_discord_can_both_be_linked(client: Client, discord: DiscordRoundTrip) -> None:
    user = verified_user()
    SocialAccount.objects.create(user=user, provider="steam", uid="76561198000000001")
    client.force_login(user)

    discord(client, DISCORD_ID, process="connect")

    assert set(SocialAccount.objects.values_list("provider", flat=True)) == {"steam", "discord"}
