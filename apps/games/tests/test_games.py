from typing import Any

import pytest
from django.db import IntegrityError
from rest_framework.test import APIClient

from apps.games.models import Game, GameSlug, ParticipantType, ResultVerification
from apps.games.tests.factories import GameFactory, SoloGameFactory, seeded_game

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("slug", "participant_type", "roster", "subs", "verification"),
    [
        (GameSlug.CS2, ParticipantType.TEAM, 5, 2, ResultVerification.MANUAL),
        (GameSlug.DOTA2, ParticipantType.TEAM, 5, 2, ResultVerification.OPENDOTA),
        (GameSlug.WILDRIFT, ParticipantType.TEAM, 5, 2, ResultVerification.MANUAL),
        (GameSlug.HEARTHSTONE, ParticipantType.SOLO, 1, 0, ResultVerification.MANUAL),
    ],
)
def test_disciplines_are_seeded(
    slug: GameSlug, participant_type: str, roster: int, subs: int, verification: str
) -> None:
    game = seeded_game(slug)

    assert game.name == slug.label
    assert (game.participant_type, game.roster_size, game.max_substitutes) == (
        participant_type,
        roster,
        subs,
    )
    assert game.result_verification == verification
    assert game.allowed_series == [1, 3, 5]
    assert game.is_active


def test_team_and_solo_games() -> None:
    assert seeded_game(GameSlug.CS2).is_team
    assert not seeded_game(GameSlug.HEARTHSTONE).is_team


@pytest.mark.parametrize(
    "overrides",
    [
        {"participant_type": ParticipantType.SOLO, "roster_size": 5, "max_substitutes": 0},
        {"participant_type": ParticipantType.SOLO, "roster_size": 1, "max_substitutes": 1},
        {"participant_type": ParticipantType.TEAM, "roster_size": 1, "max_substitutes": 0},
        {"roster_size": 2, "max_substitutes": 3},
        {"allowed_series": []},
        {"allowed_series": [2]},
    ],
    ids=["solo-roster", "solo-subs", "team-of-one", "subs-above-roster", "no-series", "bo2"],
)
def test_invalid_games_are_rejected_by_database(overrides: dict[str, Any]) -> None:
    with pytest.raises(IntegrityError):
        GameFactory.create(**overrides)


def test_slug_is_unique() -> None:
    with pytest.raises(IntegrityError):
        GameFactory.create(slug=GameSlug.CS2)


def test_api_lists_active_games_without_auth(api_client: APIClient) -> None:
    Game.objects.filter(slug=GameSlug.WILDRIFT).update(is_active=False)
    SoloGameFactory.create(is_active=False)

    response = api_client.get("/api/v1/games/")

    assert response.status_code == 200
    data = response.json()
    assert [g["slug"] for g in data] == ["cs2", "dota2", "hearthstone"]
    assert data[0] == {
        "slug": "cs2",
        "name": "Counter-Strike 2",
        "participant_type": "team",
        "roster_size": 5,
        "max_substitutes": 2,
        "allowed_series": [1, 3, 5],
        "result_verification": "manual",
        "external_id_kind": "steam_id64",
        "account_regions": [],
        "tournament_regions": [
            {"value": v, "label": label}
            for v, label in [
                ("eu", "Европа"),
                ("cis", "СНГ"),
                ("na", "Северная Америка"),
                ("sa", "Южная Америка"),
                ("asia", "Азия"),
                ("oce", "Океания"),
            ]
        ],
    }


def test_api_exposes_account_regions(api_client: APIClient) -> None:
    data = {g["slug"]: g for g in api_client.get("/api/v1/games/").json()}

    assert data["wildrift"]["external_id_kind"] == "riot_id"
    assert [r["label"] for r in data["wildrift"]["account_regions"]] == ["RU", "EUW", "EUNE", "TR"]
    assert data["hearthstone"]["external_id_kind"] == "battletag"
    assert [r["value"] for r in data["hearthstone"]["account_regions"]] == [
        "hs_americas",
        "hs_europe",
        "hs_apac",
    ]


def test_api_is_read_only(api_client: APIClient) -> None:
    assert api_client.post("/api/v1/games/", {}, format="json").status_code == 405
