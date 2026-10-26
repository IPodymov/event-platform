from typing import Any

import pytest
from django.db import IntegrityError
from rest_framework.test import APIClient

from apps.games.models import Game, GameSlug, ParticipantType
from apps.games.tests.factories import GameFactory, SoloGameFactory

pytestmark = pytest.mark.django_db


def test_team_and_solo_games() -> None:
    assert GameFactory.create().is_team
    assert not SoloGameFactory.create().is_team


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
    GameFactory.create()

    with pytest.raises(IntegrityError):
        Game.objects.create(
            name="Dup",
            slug=GameSlug.CS2,
            participant_type="team",
            roster_size=5,
            allowed_series=[1],
        )


def test_api_lists_active_games_without_auth(api_client: APIClient) -> None:
    GameFactory.create()
    SoloGameFactory.create(is_active=False)

    response = api_client.get("/api/v1/games/")

    assert response.status_code == 200
    assert response.json() == [
        {
            "slug": "cs2",
            "name": "Counter-Strike 2",
            "participant_type": "team",
            "roster_size": 5,
            "max_substitutes": 2,
            "allowed_series": [1, 3, 5],
            "result_verification": "manual",
        }
    ]


def test_api_is_read_only(api_client: APIClient) -> None:
    assert api_client.post("/api/v1/games/", {}, format="json").status_code == 405
