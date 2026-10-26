from typing import Any

import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.test import Client
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts import game_accounts
from apps.accounts.exceptions import (
    GameAccountExistsError,
    GameAccountTakenError,
    InvalidExternalIdError,
    InvalidRegionError,
    SteamGameAccountError,
    VerificationNotAllowedError,
)
from apps.accounts.models import GameAccount, User
from apps.accounts.tests.factories import UserFactory
from apps.games.models import GameSlug
from apps.games.regions import Region
from apps.games.tests.factories import seeded_game

pytestmark = pytest.mark.django_db

API = "/api/v1/me/game-accounts/"
STEAM_ID = "76561198000000001"


def link_wildrift(user: User, riot_id: str = "Faker#KR1") -> GameAccount:
    return game_accounts.game_account_link(
        user=user, game=seeded_game(GameSlug.WILDRIFT), external_id=riot_id, region=Region.WR_EUW
    )


# --- manual accounts ---------------------------------------------------------


@pytest.mark.parametrize(
    ("slug", "external_id", "region"),
    [
        (GameSlug.WILDRIFT, "Faker#KR1", Region.WR_RU),
        (GameSlug.WILDRIFT, "Some Name#EUW", Region.WR_EUW),
        (GameSlug.HEARTHSTONE, "Thijs#2345", Region.HS_EUROPE),
        (GameSlug.HEARTHSTONE, "Игрок#12345", Region.HS_EUROPE),
    ],
)
def test_link_manual_account_awaits_verification(
    slug: GameSlug, external_id: str, region: str
) -> None:
    account = game_accounts.game_account_link(
        user=UserFactory.create(),
        game=seeded_game(slug),
        external_id=f" {external_id} ",
        region=region,
    )

    assert account.external_id == external_id
    assert not account.verified


@pytest.mark.parametrize(
    ("slug", "external_id"),
    [
        (GameSlug.WILDRIFT, "NoTag"),
        (GameSlug.WILDRIFT, "ab#EUW"),
        (GameSlug.WILDRIFT, "Name#TOOLONG"),
        (GameSlug.HEARTHSTONE, "Name#12"),
        (GameSlug.HEARTHSTONE, "1Name#1234"),
        (GameSlug.HEARTHSTONE, "Name#ABCD"),
    ],
)
def test_link_rejects_malformed_ids(slug: GameSlug, external_id: str) -> None:
    region = Region.WR_RU if slug == GameSlug.WILDRIFT else Region.HS_EUROPE
    with pytest.raises(InvalidExternalIdError):
        game_accounts.game_account_link(
            user=UserFactory.create(),
            game=seeded_game(slug),
            external_id=external_id,
            region=region,
        )


@pytest.mark.parametrize("region", ["", Region.HS_EUROPE, Region.EU])
def test_link_rejects_region_of_another_game(region: str) -> None:
    with pytest.raises(InvalidRegionError):
        game_accounts.game_account_link(
            user=UserFactory.create(),
            game=seeded_game(GameSlug.WILDRIFT),
            external_id="Faker#KR1",
            region=region,
        )


@pytest.mark.parametrize("slug", [GameSlug.CS2, GameSlug.DOTA2])
def test_steam_games_cannot_be_linked_manually(slug: GameSlug) -> None:
    with pytest.raises(SteamGameAccountError):
        game_accounts.game_account_link(
            user=UserFactory.create(), game=seeded_game(slug), external_id=STEAM_ID, region=""
        )


def test_one_account_per_game() -> None:
    user = UserFactory.create()
    link_wildrift(user)

    with pytest.raises(GameAccountExistsError):
        link_wildrift(user, "Other#EUW")


def test_account_cannot_belong_to_two_players_ignoring_case() -> None:
    link_wildrift(UserFactory.create(), "Faker#KR1")

    with pytest.raises(GameAccountTakenError):
        link_wildrift(UserFactory.create(), "FAKER#kr1")


def test_update_resets_verification_only_when_id_changes() -> None:
    moderator = UserFactory.create(is_staff=True)
    account = link_wildrift(UserFactory.create())
    game_accounts.game_account_set_verified(account=account, moderator=moderator, verified=True)

    game_accounts.game_account_update(account=account, external_id="faker#kr1", region=Region.WR_RU)
    assert account.verified

    game_accounts.game_account_update(account=account, external_id="Other#KR1", region=Region.WR_RU)
    account.refresh_from_db()
    assert not account.verified
    assert account.verified_by is None


def test_delete_manual_account() -> None:
    account = link_wildrift(UserFactory.create())

    game_accounts.game_account_delete(account=account)

    assert not GameAccount.objects.exists()


# --- Steam sync --------------------------------------------------------------


def test_sync_creates_verified_steam_game_accounts() -> None:
    user = UserFactory.create()
    SocialAccount.objects.create(user=user, provider="steam", uid=STEAM_ID)

    game_accounts.sync_steam_game_accounts(user=user)

    accounts = GameAccount.objects.filter(user=user)
    assert {a.game.slug for a in accounts} == {"cs2", "dota2"}
    assert all(a.verified and a.external_id == STEAM_ID and a.region == "" for a in accounts)


def test_sync_removes_steam_game_accounts_after_unlink() -> None:
    user = UserFactory.create()
    social = SocialAccount.objects.create(user=user, provider="steam", uid=STEAM_ID)
    game_accounts.sync_steam_game_accounts(user=user)
    link_wildrift(user)

    social.delete()
    game_accounts.sync_steam_game_accounts(user=user)

    assert [a.game.slug for a in GameAccount.objects.filter(user=user)] == ["wildrift"]


def test_steam_game_accounts_cannot_be_deleted_directly() -> None:
    user = UserFactory.create()
    SocialAccount.objects.create(user=user, provider="steam", uid=STEAM_ID)
    game_accounts.sync_steam_game_accounts(user=user)

    with pytest.raises(SteamGameAccountError):
        game_accounts.game_account_delete(account=GameAccount.objects.get(game__slug="cs2"))


def test_unlinking_steam_in_ui_removes_game_accounts(client: Client) -> None:
    user = UserFactory.create()
    # allauth only allows disconnecting when the user keeps a verified email to sign in with.
    EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
    social = SocialAccount.objects.create(user=user, provider="steam", uid=STEAM_ID)
    game_accounts.sync_steam_game_accounts(user=user)
    client.force_login(user)

    client.post(reverse("socialaccount_connections"), {"account": social.pk})

    assert not GameAccount.objects.filter(user=user).exists()


# --- verification ------------------------------------------------------------


def test_staff_verifies_account() -> None:
    moderator = UserFactory.create(is_staff=True)
    account = link_wildrift(UserFactory.create())

    game_accounts.game_account_set_verified(account=account, moderator=moderator, verified=True)

    account.refresh_from_db()
    assert account.verified
    assert account.verified_by == moderator
    assert account.verified_at is not None


def test_non_staff_cannot_verify() -> None:
    account = link_wildrift(UserFactory.create())

    with pytest.raises(VerificationNotAllowedError):
        game_accounts.game_account_set_verified(
            account=account, moderator=UserFactory.create(), verified=True
        )


def test_admin_verify_action(admin_client: Client) -> None:
    account = link_wildrift(UserFactory.create())

    response = admin_client.post(
        reverse("admin:accounts_gameaccount_changelist"),
        {"action": "verify", "_selected_action": [account.pk]},
    )

    assert response.status_code == 302
    account.refresh_from_db()
    assert account.verified


# --- API ---------------------------------------------------------------------


@pytest.fixture
def player(api_client: APIClient) -> User:
    user = UserFactory.create()
    api_client.force_authenticate(user)
    return user


def test_api_create_and_list(api_client: APIClient, player: User) -> None:
    response = api_client.post(
        API,
        {"game": "hearthstone", "external_id": "Thijs#2345", "region": "hs_europe"},
        format="json",
    )

    assert response.status_code == 201, response.json()
    assert response.json() == {
        "id": response.json()["id"],
        "game": "hearthstone",
        "external_id": "Thijs#2345",
        "region": "hs_europe",
        "verified": False,
    }
    assert [a["game"] for a in api_client.get(API).json()] == ["hearthstone"]


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"game": "wildrift", "external_id": "bad", "region": "wr_ru"}, "external_id"),
        ({"game": "wildrift", "external_id": "Faker#KR1", "region": "hs_europe"}, "region"),
        ({"game": "cs2", "external_id": STEAM_ID, "region": ""}, "game"),
        ({"game": "chess", "external_id": "x#123", "region": ""}, "game"),
    ],
)
def test_api_create_errors(
    api_client: APIClient, player: User, payload: dict[str, Any], field: str
) -> None:
    response = api_client.post(API, payload, format="json")

    assert response.status_code == 400
    assert field in response.json()


def test_api_create_taken_account(api_client: APIClient, player: User) -> None:
    link_wildrift(UserFactory.create())

    response = api_client.post(
        API, {"game": "wildrift", "external_id": "faker#kr1", "region": "wr_euw"}, format="json"
    )

    assert response.status_code == 400
    assert "external_id" in response.json()


def test_api_update_and_delete(api_client: APIClient, player: User) -> None:
    account = link_wildrift(player)
    url = f"{API}{account.pk}/"

    response = api_client.patch(url, {"region": "wr_tr"}, format="json")
    assert response.status_code == 200
    assert response.json()["region"] == "wr_tr"

    assert api_client.delete(url).status_code == 204
    assert not GameAccount.objects.exists()


def test_api_cannot_touch_someone_elses_account(api_client: APIClient, player: User) -> None:
    account = link_wildrift(UserFactory.create())

    assert (
        api_client.patch(f"{API}{account.pk}/", {"region": "wr_tr"}, format="json").status_code
        == 404
    )
    assert api_client.delete(f"{API}{account.pk}/").status_code == 404


def test_api_requires_authentication(api_client: APIClient) -> None:
    assert api_client.get(API).status_code == 403


# --- page --------------------------------------------------------------------


def test_page_adds_and_removes_account(client: Client) -> None:
    user = UserFactory.create()
    client.force_login(user)
    url = reverse("accounts:game_accounts")

    response = client.post(url, {"game": "wildrift", "external_id": "Faker#KR1", "region": "wr_ru"})
    assert response.status_code == 302
    account = GameAccount.objects.get(user=user)
    assert "Faker#KR1" in client.get(url).content.decode()

    client.post(reverse("accounts:game_account_delete", args=[account.pk]))
    assert not GameAccount.objects.exists()


def test_page_shows_service_errors(client: Client) -> None:
    client.force_login(UserFactory.create())

    response = client.post(
        reverse("accounts:game_accounts"),
        {"game": "wildrift", "external_id": "Faker#KR1", "region": "hs_europe"},
    )

    assert response.status_code == 200
    assert response.context["form"].errors["region"]
