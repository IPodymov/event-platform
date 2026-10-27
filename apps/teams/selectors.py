from collections.abc import Iterable
from dataclasses import dataclass

from django.db.models import Case, Count, OuterRef, Prefetch, QuerySet, Subquery, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.accounts.models import GameAccount, User
from apps.games.models import Game
from apps.teams.models import (
    InviteStatus,
    RosterAccountStatus,
    Team,
    TeamInvite,
    TeamMembership,
)


def active_memberships() -> QuerySet[TeamMembership]:
    return TeamMembership.objects.filter(left_at__isnull=True)


def has_active_team(user: User, game: Game) -> bool:
    return active_memberships().filter(user=user, game=game).exists()


def is_team_name_taken(game: Game, name: str) -> bool:
    return Team.objects.filter(game=game, name__iexact=name).exists()


def is_team_tag_taken(game: Game, tag: str) -> bool:
    return Team.objects.filter(game=game, tag__iexact=tag).exists()


def list_teams(*, game_slug: str | None = None) -> QuerySet[Team]:
    """Active (not disbanded) teams."""
    teams = Team.objects.filter(disbanded_at__isnull=True).select_related(
        "game", "captain__profile"
    )
    if game_slug:
        teams = teams.filter(game__slug=game_slug)
    return teams


def with_account_status(memberships: QuerySet[TeamMembership]) -> QuerySet[TeamMembership]:
    """Annotate ``account_status``: the member's game account for the team's discipline."""
    account = GameAccount.objects.filter(user=OuterRef("user"), game=OuterRef("game")).annotate(
        status=Case(
            When(verified=True, then=Value(RosterAccountStatus.VERIFIED)),
            default=Value(RosterAccountStatus.UNVERIFIED),
        )
    )
    return memberships.annotate(
        account_status=Coalesce(
            Subquery(account.values("status")[:1]), Value(RosterAccountStatus.MISSING)
        )
    )


@dataclass(frozen=True)
class RosterAccountIssues:
    missing: int
    unverified: int

    @property
    def all_linked(self) -> bool:
        # Unverified accounts are only flagged; they do not stop the team (decisions.md).
        return self.missing == 0


def roster_account_issues(roster: Iterable[TeamMembership]) -> RosterAccountIssues:
    """Count members of an annotated roster (see ``with_account_status``) per problem."""
    statuses = [member.account_status for member in roster]  # type: ignore[attr-defined]
    return RosterAccountIssues(
        missing=statuses.count(RosterAccountStatus.MISSING),
        unverified=statuses.count(RosterAccountStatus.UNVERIFIED),
    )


def get_account_status(user: User, game: Game) -> RosterAccountStatus:
    verified = (
        GameAccount.objects.filter(user=user, game=game).values_list("verified", flat=True).first()
    )
    if verified is None:
        return RosterAccountStatus.MISSING
    return RosterAccountStatus.VERIFIED if verified else RosterAccountStatus.UNVERIFIED


def get_team_with_roster(team_id: int) -> Team | None:
    """The team with its active members prefetched as ``roster``.

    Members come with their profiles and an ``account_status`` annotation.
    """
    roster = with_account_status(
        active_memberships().select_related("user__profile").order_by("joined_at")
    )
    return (
        Team.objects.select_related("game", "captain__profile")
        .prefetch_related(Prefetch("memberships", queryset=roster, to_attr="roster"))
        .filter(pk=team_id)
        .first()
    )


def count_active_roles(team: Team) -> dict[str, int]:
    """Active members per role, e.g. {"captain": 1, "player": 3}."""
    counts = active_memberships().filter(team=team).values("role").annotate(n=Count("id"))
    return {row["role"]: row["n"] for row in counts}


def is_team_member(team: Team, user: User) -> bool:
    return active_memberships().filter(team=team, user=user).exists()


def pending_invites() -> QuerySet[TeamInvite]:
    return TeamInvite.objects.filter(status=InviteStatus.PENDING, expires_at__gt=timezone.now())


def list_team_invites(team: Team) -> QuerySet[TeamInvite]:
    return pending_invites().filter(team=team).select_related("invitee__profile")


def list_user_invites(user: User) -> QuerySet[TeamInvite]:
    return (
        pending_invites().filter(invitee=user).select_related("team__game", "created_by__profile")
    )


def get_invite_by_token(token: str) -> TeamInvite | None:
    return TeamInvite.objects.select_related("team__game", "invitee").filter(token=token).first()
