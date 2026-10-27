from django.db.models import Count, Prefetch, QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.games.models import Game
from apps.teams.models import InviteStatus, Team, TeamInvite, TeamMembership


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


def get_team_with_roster(team_id: int) -> Team | None:
    """The team with its active members (and their profiles) prefetched as ``roster``."""
    roster = active_memberships().select_related("user__profile").order_by("joined_at")
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
