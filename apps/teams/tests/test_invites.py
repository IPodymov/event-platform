import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.teams import services
from apps.teams.exceptions import (
    AlreadyInTeamError,
    AlreadyInvitedError,
    AlreadyMemberError,
    InviteNotActiveError,
    NotInviteeError,
    NotTeamCaptainError,
    PlayerNotFoundError,
    RosterFullError,
)
from apps.teams.models import InviteStatus, Team, TeamInvite, TeamMembership, TeamRole
from apps.teams.tests.factories import TeamFactory, TeamMembershipFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def team() -> Team:
    return TeamFactory.create(captain__profile__nickname="cap")


def invite(team: Team, nickname: str | None = None, role: str = TeamRole.PLAYER) -> TeamInvite:
    return services.invite_create(by=team.captain, team=team, nickname=nickname, role=role)


def fill(team: Team, role: str, count: int) -> None:
    for _ in range(count):
        TeamMembershipFactory.create(team=team, role=role)


# --- create ------------------------------------------------------------------


def test_personal_invite(team: Team) -> None:
    player = UserFactory.create(profile__nickname="Rookie")

    created = invite(team, "rookie")

    assert created.invitee == player
    assert created.status == InviteStatus.PENDING
    assert len(created.token) >= 40
    assert created.expires_at > timezone.now() + timedelta(days=6)


def test_link_invite(team: Team) -> None:
    created = invite(team)

    assert created.is_link


def test_only_captain_invites(team: Team) -> None:
    member = TeamMembershipFactory.create(team=team).user

    with pytest.raises(NotTeamCaptainError):
        services.invite_create(by=member, team=team)


@pytest.mark.parametrize("nickname", ["ghost", "inactive"])
def test_invitee_must_exist_and_be_active(team: Team, nickname: str) -> None:
    UserFactory.create(profile__nickname="inactive", is_active=False)

    with pytest.raises(PlayerNotFoundError):
        invite(team, nickname)


def test_cannot_invite_member(team: Team) -> None:
    with pytest.raises(AlreadyMemberError):
        invite(team, "cap")


def test_one_pending_invite_per_player(team: Team) -> None:
    UserFactory.create(profile__nickname="dup")
    invite(team, "dup")

    with pytest.raises(AlreadyInvitedError):
        invite(team, "dup")


def test_expired_invite_can_be_replaced(team: Team) -> None:
    UserFactory.create(profile__nickname="late")
    old = invite(team, "late")
    TeamInvite.objects.filter(pk=old.pk).update(expires_at=timezone.now() - timedelta(minutes=1))

    invite(team, "late")

    old.refresh_from_db()
    assert old.status == InviteStatus.REVOKED


def test_cannot_invite_into_full_role(team: Team) -> None:
    fill(team, TeamRole.SUBSTITUTE, 2)

    with pytest.raises(RosterFullError):
        invite(team, role=TeamRole.SUBSTITUTE)


# --- accept / decline / revoke ----------------------------------------------


def test_accept_personal_invite(team: Team) -> None:
    player = UserFactory.create(profile__nickname="joiner")
    created = invite(team, "joiner", role=TeamRole.SUBSTITUTE)

    membership = services.invite_accept(user=player, invite=created)

    assert (membership.team, membership.role, membership.game) == (
        team,
        TeamRole.SUBSTITUTE,
        team.game,
    )
    created.refresh_from_db()
    assert created.status == InviteStatus.ACCEPTED


def test_link_invite_serves_several_players(team: Team) -> None:
    link = invite(team)

    for _ in range(3):
        services.invite_accept(user=UserFactory.create(), invite=link)

    link.refresh_from_db()
    assert link.status == InviteStatus.PENDING
    assert TeamMembership.objects.filter(team=team, role=TeamRole.PLAYER).count() == 3


def test_personal_invite_is_for_invitee_only(team: Team) -> None:
    UserFactory.create(profile__nickname="target")
    created = invite(team, "target")

    with pytest.raises(NotInviteeError):
        services.invite_accept(user=UserFactory.create(), invite=created)


def test_accept_requires_no_other_team_in_game(team: Team) -> None:
    player = TeamMembershipFactory.create(team=TeamFactory.create()).user

    with pytest.raises(AlreadyInTeamError):
        services.invite_accept(user=player, invite=invite(team))


def test_accept_rejects_existing_member(team: Team) -> None:
    with pytest.raises(AlreadyMemberError):
        services.invite_accept(user=team.captain, invite=invite(team))


def test_accept_respects_roster_size(team: Team) -> None:
    link = invite(team)
    fill(team, TeamRole.PLAYER, 4)  # captain + 4 players = 5

    with pytest.raises(RosterFullError):
        services.invite_accept(user=UserFactory.create(), invite=link)


@pytest.mark.parametrize("status", [InviteStatus.DECLINED, InviteStatus.REVOKED])
def test_closed_invite_cannot_be_accepted(team: Team, status: str) -> None:
    player = UserFactory.create(profile__nickname="p")
    created = invite(team, "p")
    TeamInvite.objects.filter(pk=created.pk).update(status=status)

    with pytest.raises(InviteNotActiveError):
        services.invite_accept(user=player, invite=created)


def test_expired_invite_cannot_be_accepted(team: Team) -> None:
    link = invite(team)
    TeamInvite.objects.filter(pk=link.pk).update(expires_at=timezone.now())

    with pytest.raises(InviteNotActiveError):
        services.invite_accept(user=UserFactory.create(), invite=link)


def test_decline(team: Team) -> None:
    player = UserFactory.create(profile__nickname="no")
    created = invite(team, "no")

    services.invite_decline(user=player, invite=created)

    created.refresh_from_db()
    assert created.status == InviteStatus.DECLINED
    with pytest.raises(NotInviteeError):
        services.invite_decline(user=UserFactory.create(), invite=created)


def test_revoke_by_captain_only(team: Team) -> None:
    link = invite(team)
    with pytest.raises(NotTeamCaptainError):
        services.invite_revoke(by=UserFactory.create(), invite=link)

    services.invite_revoke(by=team.captain, invite=link)

    link.refresh_from_db()
    assert link.status == InviteStatus.REVOKED


# serialized_rollback restores the disciplines seeded by migrations after the flush.
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_accepts_do_not_overfill_roster() -> None:
    team = TeamFactory.create()
    link = services.invite_create(by=team.captain, team=team, role=TeamRole.SUBSTITUTE)
    players: list[User] = [UserFactory.create() for _ in range(5)]
    outcomes: list[str] = []

    def accept(player: User) -> None:
        try:
            services.invite_accept(user=player, invite=link)
            outcomes.append("ok")
        except RosterFullError:
            outcomes.append("full")
        finally:
            connection.close()

    threads = [threading.Thread(target=accept, args=(p,)) for p in players]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(outcomes) == ["full", "full", "full", "ok", "ok"]
    assert TeamMembership.objects.filter(team=team, role=TeamRole.SUBSTITUTE).count() == 2


# --- API ---------------------------------------------------------------------


def test_api_captain_creates_and_lists_invites(api_client: APIClient, team: Team) -> None:
    UserFactory.create(profile__nickname="guest")
    api_client.force_authenticate(team.captain)

    response = api_client.post(
        f"/api/v1/teams/{team.pk}/invites/", {"nickname": "guest"}, format="json"
    )
    link = api_client.post(f"/api/v1/teams/{team.pk}/invites/", {}, format="json")

    assert response.status_code == 201
    assert response.json()["invitee"] == "guest"
    assert link.json()["invitee"] is None
    assert link.json()["url"].endswith(f"/invites/{link.json()['token']}/")
    listed = api_client.get(f"/api/v1/teams/{team.pk}/invites/").json()
    assert {i["id"] for i in listed} == {response.json()["id"], link.json()["id"]}


def test_api_non_captain_gets_403(api_client: APIClient, team: Team) -> None:
    api_client.force_authenticate(UserFactory.create())

    assert (
        api_client.post(f"/api/v1/teams/{team.pk}/invites/", {}, format="json").status_code == 403
    )
    assert api_client.get(f"/api/v1/teams/{team.pk}/invites/").status_code == 403


def test_api_invite_errors(api_client: APIClient, team: Team) -> None:
    api_client.force_authenticate(team.captain)

    response = api_client.post(
        f"/api/v1/teams/{team.pk}/invites/", {"nickname": "nobody"}, format="json"
    )

    assert response.status_code == 400
    assert "nickname" in response.json()


def test_api_my_invites_accept_and_decline(api_client: APIClient, team: Team) -> None:
    player = UserFactory.create(profile__nickname="me")
    other_team = TeamFactory.create(game=team.game)
    first = invite(team, "me")
    second = invite(other_team, "me")
    api_client.force_authenticate(player)

    assert {i["id"] for i in api_client.get("/api/v1/me/invites/").json()} == {first.pk, second.pk}
    assert api_client.post(f"/api/v1/invites/{second.token}/decline/").status_code == 204
    accepted = api_client.post(f"/api/v1/invites/{first.token}/accept/")

    assert accepted.status_code == 201
    assert accepted.json()["role"] == "player"
    assert api_client.get("/api/v1/me/invites/").json() == []


def test_api_accept_someone_elses_invite_403(api_client: APIClient, team: Team) -> None:
    UserFactory.create(profile__nickname="owner")
    created = invite(team, "owner")
    api_client.force_authenticate(UserFactory.create())

    assert api_client.post(f"/api/v1/invites/{created.token}/accept/").status_code == 403


def test_api_revoke(api_client: APIClient, team: Team) -> None:
    link = invite(team)
    api_client.force_authenticate(team.captain)

    response = api_client.delete(f"/api/v1/teams/{team.pk}/invites/{link.pk}/")

    assert response.status_code == 204
    assert api_client.post(f"/api/v1/invites/{link.token}/accept/").status_code in (400, 403)


def test_api_unknown_token_404(api_client: APIClient) -> None:
    api_client.force_authenticate(UserFactory.create())

    assert api_client.get("/api/v1/invites/nope/").status_code == 404


# --- pages -------------------------------------------------------------------


def test_captain_page_creates_link_and_player_joins(client: Client, team: Team) -> None:
    client.force_login(team.captain)
    client.post(reverse("teams:invite_create", args=[team.pk]), {"nickname": "", "role": "player"})
    link = TeamInvite.objects.get(team=team)
    assert link.token in client.get(reverse("teams:detail", args=[team.pk])).content.decode()

    player = UserFactory.create()
    client.force_login(player)
    response = client.post(reverse("teams:invite", args=[link.token]), {"action": "accept"})

    assert response["Location"] == reverse("teams:detail", args=[team.pk])
    assert TeamMembership.objects.filter(team=team, user=player).exists()


def test_invite_page_shows_errors(client: Client, team: Team) -> None:
    link = invite(team)
    client.force_login(team.captain)

    response = client.post(
        reverse("teams:invite", args=[link.token]), {"action": "accept"}, follow=True
    )

    assert response.status_code == 200
    assert list(response.context["messages"])


def test_my_invites_page(client: Client, team: Team) -> None:
    player = UserFactory.create(profile__nickname="listed")
    invite(team, "listed")
    client.force_login(player)

    assert team.name in client.get(reverse("teams:my_invites")).content.decode()
