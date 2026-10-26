from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
from openid.consumer import consumer

from apps.accounts import services
from apps.accounts.exceptions import SteamAlreadyLinkedError, SteamSignupNotAllowedError
from apps.accounts.models import User
from apps.accounts.selectors import get_steam_id
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

STEAM_ID = "76561198000000001"
OTHER_STEAM_ID = "76561198000000002"

SteamRoundTrip = Callable[..., Any]


@pytest.fixture
def steam() -> Iterator[SteamRoundTrip]:
    """Fake the Steam side of the OpenID exchange and the Web API lookup."""

    def round_trip(client: Client, steam_id: str, process: str = "login") -> Any:
        openid_response = SimpleNamespace(
            status=consumer.SUCCESS,
            identity_url=f"https://steamcommunity.com/openid/id/{steam_id}",
        )
        summary = {"steamid": steam_id, "personaname": "s1mple", "avatarfull": "https://a/b.jpg"}
        with (
            mock.patch(
                "allauth.socialaccount.providers.steam.views.SteamOpenIDCallbackView"
                ".get_openid_response",
                return_value=openid_response,
            ),
            mock.patch(
                "allauth.socialaccount.providers.steam.provider.request_steam_account_summary",
                return_value=summary,
            ),
        ):
            response = client.post(reverse("steam_login"), {"process": process})
            assert response.status_code == 302
            assert response["Location"].startswith("https://steamcommunity.com/openid/login")
            return client.get(reverse("steam_callback"))

    fake_auth_request = mock.Mock()
    fake_auth_request.redirectURL.return_value = "https://steamcommunity.com/openid/login?x=1"
    with mock.patch(
        "allauth.socialaccount.providers.steam.provider._openid_consumer"
    ) as openid_consumer:
        openid_consumer.return_value.begin.return_value = fake_auth_request
        yield round_trip


def verified_user(email: str = "player@example.com") -> User:
    user = UserFactory.create(email=email)
    EmailAddress.objects.create(user=user, email=email, primary=True, verified=True)
    return user


def link_steam(user: User, steam_id: str = STEAM_ID) -> SocialAccount:
    return SocialAccount.objects.create(user=user, provider="steam", uid=steam_id)


def logged_in_user_id(client: Client) -> int | None:
    value = client.session.get("_auth_user_id")
    return int(value) if value else None


def messages_text(response: Any) -> str:
    return " ".join(str(m) for m in get_messages(response.wsgi_request))


def test_connect_links_steam_to_current_user(client: Client, steam: SteamRoundTrip) -> None:
    user = verified_user()
    client.force_login(user)

    response = steam(client, STEAM_ID, process="connect")

    assert response.status_code == 302
    assert get_steam_id(user) == STEAM_ID
    account = SocialAccount.objects.get(user=user)
    assert account.extra_data["personaname"] == "s1mple"


def test_login_with_linked_steam(client: Client, steam: SteamRoundTrip) -> None:
    user = verified_user()
    link_steam(user)

    response = steam(client, STEAM_ID)

    assert response.status_code == 302
    assert logged_in_user_id(client) == user.pk


def test_unlinked_steam_cannot_sign_up(client: Client, steam: SteamRoundTrip) -> None:
    response = steam(client, STEAM_ID)

    assert response.status_code == 302
    assert response["Location"] == reverse("account_login")
    assert logged_in_user_id(client) is None
    assert not User.objects.exists()
    assert not SocialAccount.objects.exists()
    assert "Steam" in messages_text(response)


def test_second_steam_account_is_refused(client: Client, steam: SteamRoundTrip) -> None:
    user = verified_user()
    link_steam(user)
    client.force_login(user)

    response = steam(client, OTHER_STEAM_ID, process="connect")

    assert response["Location"] == reverse("socialaccount_connections")
    assert list(SocialAccount.objects.values_list("uid", flat=True)) == [STEAM_ID]


def test_steam_linked_to_someone_else_is_not_moved(client: Client, steam: SteamRoundTrip) -> None:
    owner = verified_user("owner@example.com")
    link_steam(owner)
    intruder = verified_user("intruder@example.com")
    client.force_login(intruder)

    steam(client, STEAM_ID, process="connect")

    assert get_steam_id(owner) == STEAM_ID
    assert get_steam_id(intruder) is None


def test_disconnect_steam(client: Client) -> None:
    user = verified_user()
    account = link_steam(user)
    client.force_login(user)

    response = client.post(reverse("socialaccount_connections"), {"account": account.pk})

    assert response.status_code == 302
    assert get_steam_id(user) is None


def test_validate_steam_link_allows_relinking_same_account() -> None:
    user = verified_user()
    link_steam(user)

    services.validate_steam_link(user=user, steam_id=STEAM_ID)

    with pytest.raises(SteamAlreadyLinkedError):
        services.validate_steam_link(user=user, steam_id=OTHER_STEAM_ID)


def test_validate_steam_login() -> None:
    services.validate_steam_login(is_linked=True)

    with pytest.raises(SteamSignupNotAllowedError):
        services.validate_steam_login(is_linked=False)


def test_api_lists_steam_provider_and_linked_accounts(client: Client) -> None:
    user = verified_user()
    link_steam(user)
    client.force_login(user)

    config = client.get("/api/auth/browser/v1/config").json()
    providers = client.get("/api/auth/browser/v1/account/providers").json()

    assert "steam" in {p["id"] for p in config["data"]["socialaccount"]["providers"]}
    assert [a["uid"] for a in providers["data"]] == [STEAM_ID]
