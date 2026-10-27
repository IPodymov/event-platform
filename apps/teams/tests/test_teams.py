from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.accounts.tests.images import image_upload
from apps.games.models import Game, GameSlug
from apps.games.tests.factories import seeded_game
from apps.teams import services
from apps.teams.exceptions import (
    AlreadyInTeamError,
    InvalidLogoError,
    NotATeamGameError,
    TeamNameTakenError,
    TeamTagTakenError,
)
from apps.teams.models import Team, TeamMembership, TeamRole
from apps.teams.tests.factories import TeamFactory, TeamMembershipFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def cs2() -> Game:
    return seeded_game(GameSlug.CS2)


def create(user: User, game: Game, name: str = "Natus Vincere", tag: str = "NAVI") -> Team:
    return services.team_create(user=user, game=game, name=name, tag=tag)


# --- service -----------------------------------------------------------------


def test_creator_becomes_captain(cs2: Game) -> None:
    user = UserFactory.create()

    team = create(user, cs2, name="  Natus Vincere ", tag="NAVI")

    assert (team.name, team.tag, team.captain) == ("Natus Vincere", "NAVI", user)
    membership = TeamMembership.objects.get(team=team)
    assert (membership.user, membership.role, membership.game) == (user, TeamRole.CAPTAIN, cs2)
    assert membership.is_active


def test_teams_only_in_team_games() -> None:
    with pytest.raises(NotATeamGameError):
        create(UserFactory.create(), seeded_game(GameSlug.HEARTHSTONE))


def test_not_in_inactive_games(cs2: Game) -> None:
    Game.objects.filter(pk=cs2.pk).update(is_active=False)
    cs2.refresh_from_db()

    with pytest.raises(NotATeamGameError):
        create(UserFactory.create(), cs2)


def test_one_active_team_per_game(cs2: Game) -> None:
    user = UserFactory.create()
    create(user, cs2)

    with pytest.raises(AlreadyInTeamError):
        create(user, cs2, name="Other", tag="OTH")


def test_same_player_can_have_teams_in_different_games(cs2: Game) -> None:
    user = UserFactory.create()
    create(user, cs2)

    create(user, seeded_game(GameSlug.DOTA2))

    assert Team.objects.filter(captain=user).count() == 2


def test_player_who_left_can_create_new_team(cs2: Game) -> None:
    user = UserFactory.create()
    create(user, cs2)
    TeamMembership.objects.filter(user=user).update(left_at=timezone.now())

    create(user, cs2, name="Fresh", tag="NEW")


@pytest.mark.parametrize(
    ("name", "tag", "error"),
    [("NATUS VINCERE", "XX", TeamNameTakenError), ("Other", "navi", TeamTagTakenError)],
)
def test_name_and_tag_unique_per_game_ignoring_case(
    cs2: Game, name: str, tag: str, error: type[Exception]
) -> None:
    create(UserFactory.create(), cs2)

    with pytest.raises(error):
        create(UserFactory.create(), cs2, name=name, tag=tag)


def test_same_name_allowed_in_another_game(cs2: Game) -> None:
    create(UserFactory.create(), cs2)

    create(UserFactory.create(), seeded_game(GameSlug.DOTA2))


@pytest.mark.parametrize("tag", ["N", "TOOLONG", "NA VI", "НАВИ"])
def test_tag_format(cs2: Game, tag: str) -> None:
    with pytest.raises(ValidationError):
        create(UserFactory.create(), cs2, tag=tag)


def test_logo_is_reencoded(cs2: Game) -> None:
    team = services.team_create(
        user=UserFactory.create(), game=cs2, name="Logo", tag="LG", logo=image_upload()
    )

    assert team.logo.name.startswith("team_logos/") and team.logo.name.endswith(".webp")
    with Image.open(team.logo.path) as stored:
        assert max(stored.size) == 256


def test_invalid_logo_creates_nothing(cs2: Game, settings: Settings) -> None:
    with pytest.raises(InvalidLogoError):
        services.team_create(
            user=UserFactory.create(),
            game=cs2,
            name="Logo",
            tag="LG",
            logo=image_upload(fmt="GIF", name="a.gif"),
        )

    assert not Team.objects.exists()
    assert not any(Path(settings.MEDIA_ROOT).rglob("*"))


def test_database_enforces_one_active_team_per_game(cs2: Game) -> None:
    membership = TeamMembershipFactory.create(team=TeamFactory.create())

    with pytest.raises(IntegrityError):
        TeamMembershipFactory.create(team=TeamFactory.create(), user=membership.user)


def test_database_enforces_one_captain(cs2: Game) -> None:
    team = TeamFactory.create()

    with pytest.raises(IntegrityError):
        TeamMembershipFactory.create(team=team, role=TeamRole.CAPTAIN)


# --- API ---------------------------------------------------------------------


def test_api_create_team(api_client: APIClient) -> None:
    user = UserFactory.create(profile__nickname="s1mple")
    api_client.force_authenticate(user)

    response = api_client.post(
        "/api/v1/teams/", {"game": "cs2", "name": "NAVI", "tag": "NAVI"}, format="json"
    )

    assert response.status_code == 201, response.json()
    assert response.json()["captain"] == "s1mple"


def test_api_create_with_logo(api_client: APIClient) -> None:
    api_client.force_authenticate(UserFactory.create())

    response = api_client.post(
        "/api/v1/teams/",
        {"game": "dota2", "name": "Spirit", "tag": "TS", "logo": image_upload()},
        format="multipart",
    )

    assert response.status_code == 201
    assert response.json()["logo"].endswith(".webp")


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"game": "hearthstone", "name": "Solo", "tag": "SOLO"}, "game"),
        ({"game": "cs2", "name": "Taken", "tag": "NEW"}, "name"),
        ({"game": "cs2", "name": "New", "tag": "tkn"}, "tag"),
        ({"game": "cs2", "name": "New", "tag": "!"}, "tag"),
    ],
)
def test_api_create_errors(api_client: APIClient, payload: dict[str, str], field: str) -> None:
    TeamFactory.create(name="taken", tag="TKN")
    api_client.force_authenticate(UserFactory.create())

    response = api_client.post("/api/v1/teams/", payload, format="json")

    assert response.status_code == 400
    assert field in response.json()


def test_api_create_requires_login(api_client: APIClient) -> None:
    response = api_client.post(
        "/api/v1/teams/", {"game": "cs2", "name": "X", "tag": "XX"}, format="json"
    )

    assert response.status_code == 403


def test_api_list_filters_by_game(api_client: APIClient) -> None:
    TeamFactory.create(name="CS team")
    TeamFactory.create(name="Dota team", game=seeded_game(GameSlug.DOTA2))

    response = api_client.get("/api/v1/teams/", {"game": "dota2"})

    assert [t["name"] for t in response.json()["results"]] == ["Dota team"]


def test_api_detail_shows_active_roster(api_client: APIClient) -> None:
    team = TeamFactory.create(captain__profile__nickname="cap")
    TeamMembershipFactory.create(team=team, user__profile__nickname="sub", role=TeamRole.SUBSTITUTE)
    TeamMembershipFactory.create(team=team, left_at=timezone.now())

    response = api_client.get(f"/api/v1/teams/{team.pk}/")

    assert response.status_code == 200
    assert [(m["nickname"], m["role"]) for m in response.json()["roster"]] == [
        ("cap", "captain"),
        ("sub", "substitute"),
    ]


def test_api_detail_404(api_client: APIClient) -> None:
    assert api_client.get("/api/v1/teams/999999/").status_code == 404


# --- pages -------------------------------------------------------------------


def test_create_page(client: Client) -> None:
    client.force_login(UserFactory.create())

    response = client.post(
        reverse("teams:create"), {"game": "cs2", "name": "Vitality", "tag": "VIT"}
    )

    team = Team.objects.get(tag="VIT")
    assert response.status_code == 302
    assert response["Location"] == reverse("teams:detail", args=[team.pk])
    assert "Vitality" in client.get(response["Location"]).content.decode()


def test_create_page_shows_service_error(client: Client) -> None:
    user = UserFactory.create()
    TeamFactory.create(captain=user)
    client.force_login(user)

    response = client.post(reverse("teams:create"), {"game": "cs2", "name": "Two", "tag": "TWO"})

    assert response.status_code == 200
    assert response.context["form"].errors["game"]
