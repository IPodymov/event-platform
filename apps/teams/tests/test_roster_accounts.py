import pytest
from django.test import Client
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import GameAccount, User
from apps.accounts.tests.factories import UserFactory
from apps.games.models import Game, GameSlug
from apps.games.tests.factories import seeded_game
from apps.teams import services
from apps.teams.models import RosterAccountStatus, Team, TeamMembership
from apps.teams.selectors import get_team_with_roster, roster_account_issues
from apps.teams.tests.factories import TeamFactory, TeamMembershipFactory

pytestmark = pytest.mark.django_db


def link(user: User, game: Game, *, verified: bool = True) -> GameAccount:
    return GameAccount.objects.create(
        user=user, game=game, external_id=f"id-{user.pk}-{game.slug}", verified=verified
    )


@pytest.fixture
def team() -> Team:
    """CS2 team: verified captain, unverified player, player without an account."""
    team = TeamFactory.create(captain__profile__nickname="cap")
    link(team.captain, team.game)
    unverified = TeamMembershipFactory.create(team=team, user__profile__nickname="unverified")
    link(unverified.user, team.game, verified=False)
    TeamMembershipFactory.create(team=team, user__profile__nickname="missing")
    return team


def roster(team_id: int) -> list[TeamMembership]:
    team = get_team_with_roster(team_id)
    assert team is not None
    return team.roster  # type: ignore[attr-defined]


def statuses(team_id: int) -> dict[str, str]:
    return {m.user.profile.nickname: m.account_status for m in roster(team_id)}  # type: ignore[attr-defined]


def test_roster_reports_account_status_per_member(team: Team) -> None:
    assert statuses(team.pk) == {
        "cap": RosterAccountStatus.VERIFIED,
        "unverified": RosterAccountStatus.UNVERIFIED,
        "missing": RosterAccountStatus.MISSING,
    }


def test_account_of_another_game_does_not_count(team: Team) -> None:
    missing = team.memberships.get(user__profile__nickname="missing").user
    link(missing, seeded_game(GameSlug.DOTA2))

    assert statuses(team.pk)["missing"] == RosterAccountStatus.MISSING


def test_issues_summary(team: Team) -> None:
    issues = roster_account_issues(roster(team.pk))

    assert (issues.missing, issues.unverified) == (1, 1)
    assert not issues.all_linked


def test_unverified_accounts_count_as_linked(team: Team) -> None:
    missing = team.memberships.get(user__profile__nickname="missing").user
    link(missing, team.game, verified=False)
    assert roster_account_issues(roster(team.pk)).all_linked


# --- API -----------------------------------------------------------------------


def test_api_detail_shows_account_status(api_client: APIClient, team: Team) -> None:
    data = api_client.get(f"/api/v1/teams/{team.pk}/").json()

    assert {m["nickname"]: m["game_account_status"] for m in data["roster"]} == {
        "cap": "verified",
        "unverified": "unverified",
        "missing": "missing",
    }
    assert data["all_accounts_linked"] is False


def test_api_accept_reports_missing_account(api_client: APIClient) -> None:
    team = TeamFactory.create()
    invite = services.invite_create(by=team.captain, team=team)
    api_client.force_authenticate(UserFactory.create())

    response = api_client.post(f"/api/v1/invites/{invite.token}/accept/")

    assert response.status_code == 201
    assert response.json()["game_account_status"] == "missing"


# --- pages ---------------------------------------------------------------------


def test_team_page_marks_members_without_accounts(client: Client, team: Team) -> None:
    client.force_login(team.captain)

    page = client.get(reverse("teams:detail", args=[team.pk])).content.decode()

    assert "roster-account-missing" in page
    assert "roster-account-unverified" in page
    assert "roster-issues" in page


def test_member_without_account_sees_link_to_settings(client: Client, team: Team) -> None:
    client.force_login(team.memberships.get(user__profile__nickname="missing").user)

    page = client.get(reverse("teams:detail", args=[team.pk])).content.decode()

    assert reverse("accounts:game_accounts") in page


def test_outsider_sees_no_warning(client: Client, team: Team) -> None:
    client.force_login(UserFactory.create())

    page = client.get(reverse("teams:detail", args=[team.pk])).content.decode()

    assert "roster-issues" not in page


def test_invite_page_warns_without_account(client: Client) -> None:
    team = TeamFactory.create()
    invite = services.invite_create(by=team.captain, team=team)
    client.force_login(UserFactory.create())

    page = client.get(reverse("teams:invite", args=[invite.token])).content.decode()

    assert reverse("accounts:game_accounts") in page


def test_accepting_without_account_shows_warning(client: Client) -> None:
    team = TeamFactory.create()
    invite = services.invite_create(by=team.captain, team=team)
    client.force_login(UserFactory.create())

    response = client.post(
        reverse("teams:invite", args=[invite.token]), {"action": "accept"}, follow=True
    )

    levels = [m.level_tag for m in response.context["messages"]]
    assert "warning" in levels


def test_api_times_are_utc_regardless_of_profile(api_client: APIClient, team: Team) -> None:
    team.captain.profile.timezone = "Asia/Vladivostok"
    team.captain.profile.save()
    api_client.force_login(team.captain)

    data = api_client.get(f"/api/v1/teams/{team.pk}/").json()

    assert data["created_at"].endswith("Z")
    assert all(member["joined_at"].endswith("Z") for member in data["roster"])
