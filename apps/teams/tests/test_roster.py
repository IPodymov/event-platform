import pytest
from django.test import Client
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.teams import services
from apps.teams.exceptions import (
    CannotRemoveCaptainError,
    CaptainMustTransferError,
    InvalidRoleError,
    NotTeamCaptainError,
    NotTeamMemberError,
    RosterFullError,
    TeamDisbandedError,
    TeamNameTakenError,
)
from apps.teams.models import InviteStatus, Team, TeamInvite, TeamMembership, TeamRole
from apps.teams.selectors import list_teams
from apps.teams.tests.factories import TeamFactory, TeamMembershipFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def team() -> Team:
    return TeamFactory.create()


def captain_membership(team: Team) -> TeamMembership:
    return TeamMembership.objects.get(team=team, role=TeamRole.CAPTAIN, left_at__isnull=True)


def add(team: Team, role: str = TeamRole.PLAYER) -> TeamMembership:
    return TeamMembershipFactory.create(team=team, role=role)


# --- roles -------------------------------------------------------------------


def test_change_role(team: Team) -> None:
    member = add(team)

    services.member_change_role(
        by=team.captain, team=team, membership_id=member.pk, role=TeamRole.SUBSTITUTE
    )

    member.refresh_from_db()
    assert member.role == TeamRole.SUBSTITUTE


def test_change_role_respects_capacity(team: Team) -> None:
    add(team, TeamRole.SUBSTITUTE)
    add(team, TeamRole.SUBSTITUTE)
    member = add(team)

    with pytest.raises(RosterFullError):
        services.member_change_role(
            by=team.captain, team=team, membership_id=member.pk, role=TeamRole.SUBSTITUTE
        )


@pytest.mark.parametrize("role", [TeamRole.CAPTAIN, "coach"])
def test_change_role_only_to_player_or_substitute(team: Team, role: str) -> None:
    with pytest.raises(InvalidRoleError):
        services.member_change_role(
            by=team.captain, team=team, membership_id=add(team).pk, role=role
        )


def test_captain_role_cannot_be_changed(team: Team) -> None:
    with pytest.raises(CannotRemoveCaptainError):
        services.member_change_role(
            by=team.captain,
            team=team,
            membership_id=captain_membership(team).pk,
            role=TeamRole.PLAYER,
        )


def test_only_captain_manages_roster(team: Team) -> None:
    member = add(team)

    with pytest.raises(NotTeamCaptainError):
        services.member_change_role(
            by=member.user, team=team, membership_id=member.pk, role=TeamRole.SUBSTITUTE
        )
    with pytest.raises(NotTeamCaptainError):
        services.member_remove(by=member.user, team=team, membership_id=member.pk)


def test_membership_of_another_team_is_not_found(team: Team) -> None:
    stranger = add(TeamFactory.create())

    with pytest.raises(NotTeamMemberError):
        services.member_remove(by=team.captain, team=team, membership_id=stranger.pk)


# --- captaincy ---------------------------------------------------------------


def test_transfer_swaps_roles(team: Team) -> None:
    old_captain = captain_membership(team)
    substitute = add(team, TeamRole.SUBSTITUTE)

    services.captain_transfer(by=team.captain, team=team, membership_id=substitute.pk)

    team.refresh_from_db()
    old_captain.refresh_from_db()
    substitute.refresh_from_db()
    assert team.captain == substitute.user
    assert substitute.role == TeamRole.CAPTAIN
    assert old_captain.role == TeamRole.SUBSTITUTE


def test_transfer_by_non_captain(team: Team) -> None:
    member = add(team)

    with pytest.raises(NotTeamCaptainError):
        services.captain_transfer(by=member.user, team=team, membership_id=member.pk)


# --- leaving and removal -----------------------------------------------------


def test_remove_member(team: Team) -> None:
    member = add(team)

    services.member_remove(by=team.captain, team=team, membership_id=member.pk)

    member.refresh_from_db()
    assert member.left_at is not None


def test_captain_cannot_be_removed(team: Team) -> None:
    with pytest.raises(CannotRemoveCaptainError):
        services.member_remove(
            by=team.captain, team=team, membership_id=captain_membership(team).pk
        )


def test_member_leaves_and_can_join_another_team(team: Team) -> None:
    member = add(team)

    services.member_leave(user=member.user, team=team)

    other = TeamFactory.create(game=team.game)
    link = services.invite_create(by=other.captain, team=other)
    services.invite_accept(user=member.user, invite=link)


def test_captain_must_transfer_before_leaving(team: Team) -> None:
    add(team)

    with pytest.raises(CaptainMustTransferError):
        services.member_leave(user=team.captain, team=team)


def test_last_captain_leaving_disbands_team(team: Team) -> None:
    link = services.invite_create(by=team.captain, team=team)

    services.member_leave(user=team.captain, team=team)

    team.refresh_from_db()
    assert team.is_disbanded
    assert team not in list_teams()
    assert TeamInvite.objects.get(pk=link.pk).status == InviteStatus.REVOKED
    with pytest.raises(TeamDisbandedError):
        services.invite_create(by=team.captain, team=team)


def test_disbanded_team_keeps_name_and_tag(team: Team) -> None:
    services.member_leave(user=team.captain, team=team)

    with pytest.raises(TeamNameTakenError):
        services.team_create(user=UserFactory.create(), game=team.game, name=team.name, tag="NEW")


def test_non_member_cannot_leave(team: Team) -> None:
    with pytest.raises(NotTeamMemberError):
        services.member_leave(user=UserFactory.create(), team=team)


# --- API ---------------------------------------------------------------------


def test_api_roster_actions(api_client: APIClient, team: Team) -> None:
    member = add(team)
    leaver = add(team)
    api_client.force_authenticate(team.captain)
    base = f"/api/v1/teams/{team.pk}"

    patched = api_client.patch(
        f"{base}/members/{member.pk}/", {"role": "substitute"}, format="json"
    )
    assert patched.status_code == 200
    assert patched.json()["role"] == "substitute"

    assert api_client.delete(f"{base}/members/{leaver.pk}/").status_code == 204

    transferred = api_client.post(
        f"{base}/transfer-captaincy/", {"membership_id": member.pk}, format="json"
    )
    assert transferred.status_code == 200
    assert transferred.json()["captain"] == member.user.profile.nickname

    assert api_client.post(f"{base}/leave/").status_code == 204
    roster = api_client.get(f"{base}/").json()["roster"]
    assert [(m["id"], m["role"]) for m in roster] == [(member.pk, "captain")]


def test_api_non_captain_403(api_client: APIClient, team: Team) -> None:
    member = add(team)
    api_client.force_authenticate(member.user)

    response = api_client.patch(
        f"/api/v1/teams/{team.pk}/members/{member.pk}/", {"role": "substitute"}, format="json"
    )

    assert response.status_code == 403


def test_api_captain_leave_with_members_400(api_client: APIClient, team: Team) -> None:
    add(team)
    api_client.force_authenticate(team.captain)

    assert api_client.post(f"/api/v1/teams/{team.pk}/leave/").status_code == 400


# --- page --------------------------------------------------------------------


def test_page_roster_actions(client: Client, team: Team) -> None:
    member = add(team)
    client.force_login(team.captain)
    url = reverse("teams:member_action", args=[team.pk, member.pk])

    client.post(url, {"action": "set_role", "role": "substitute"})
    member.refresh_from_db()
    assert member.role == TeamRole.SUBSTITUTE

    client.post(url, {"action": "make_captain"})
    team.refresh_from_db()
    assert team.captain == member.user


def test_page_leave(client: Client, team: Team) -> None:
    member = add(team)
    client.force_login(member.user)

    response = client.post(reverse("teams:leave", args=[team.pk]))

    assert response.status_code == 302
    member.refresh_from_db()
    assert member.left_at is not None


def test_captain_page_renders_all_tags(client: Client, team: Team) -> None:
    add(team)
    services.invite_create(by=team.captain, team=team)
    client.force_login(team.captain)

    content = client.get(reverse("teams:detail", args=[team.pk])).content.decode()

    assert "{{" not in content and "{%" not in content
    assert "http://testserver/invites/" in content
