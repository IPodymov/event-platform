from typing import Any

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts import game_accounts
from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.games.models import GameSlug
from apps.games.regions import Region
from apps.games.tests.factories import seeded_game

pytestmark = pytest.mark.django_db


@pytest.fixture
def player() -> User:
    user = UserFactory.create(
        email="secret@example.com",
        profile__nickname="ZywOo",
        profile__country="FR",
        profile__bio="AWP",
    )
    game_accounts.game_account_link(
        user=user,
        game=seeded_game(GameSlug.HEARTHSTONE),
        external_id="Zywoo#1234",
        region=Region.HS_EUROPE,
    )
    return user


def test_page_shows_public_data_only(client: Client, player: User) -> None:
    response = client.get(reverse("accounts:public_profile", args=["ZywOo"]))

    content = response.content.decode()
    assert response.status_code == 200
    assert "ZywOo" in content
    assert "Zywoo#1234" in content
    assert "secret@example.com" not in content


def test_page_redirects_to_canonical_nickname(client: Client, player: User) -> None:
    response = client.get(reverse("accounts:public_profile", args=["zywoo"]))

    assert response.status_code == 301
    assert response["Location"] == reverse("accounts:public_profile", args=["ZywOo"])


@pytest.mark.parametrize("nickname", ["nobody", "ZywOo"])
def test_page_404_for_unknown_or_inactive(client: Client, player: User, nickname: str) -> None:
    User.objects.filter(pk=player.pk).update(is_active=False)

    response = client.get(reverse("accounts:public_profile", args=[nickname]))

    assert response.status_code == 404


def test_api_returns_public_profile(api_client: APIClient, player: User) -> None:
    response = api_client.get("/api/v1/players/zywoo/")

    assert response.status_code == 200
    data: dict[str, Any] = response.json()
    assert data["nickname"] == "ZywOo"
    assert data["country"]["code"] == "FR"
    assert data["game_accounts"] == [
        {
            "game": "hearthstone",
            "external_id": "Zywoo#1234",
            "region": "hs_europe",
            "verified": False,
        }
    ]
    assert "email" not in data


def test_api_404(api_client: APIClient) -> None:
    assert api_client.get("/api/v1/players/nobody/").status_code == 404


def test_api_query_count_does_not_grow_with_accounts(api_client: APIClient, player: User) -> None:
    game_accounts.game_account_link(
        user=player,
        game=seeded_game(GameSlug.WILDRIFT),
        external_id="ZywOo#EUW",
        region=Region.WR_EUW,
    )

    with CaptureQueriesContext(connection) as queries:
        api_client.get("/api/v1/players/zywoo/")

    assert len(queries) <= 3
