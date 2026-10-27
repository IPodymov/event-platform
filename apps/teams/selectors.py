from django.db.models import Prefetch, QuerySet

from apps.accounts.models import User
from apps.games.models import Game
from apps.teams.models import Team, TeamMembership


def active_memberships() -> QuerySet[TeamMembership]:
    return TeamMembership.objects.filter(left_at__isnull=True)


def has_active_team(user: User, game: Game) -> bool:
    return active_memberships().filter(user=user, game=game).exists()


def is_team_name_taken(game: Game, name: str) -> bool:
    return Team.objects.filter(game=game, name__iexact=name).exists()


def is_team_tag_taken(game: Game, tag: str) -> bool:
    return Team.objects.filter(game=game, tag__iexact=tag).exists()


def list_teams(*, game_slug: str | None = None) -> QuerySet[Team]:
    teams = Team.objects.select_related("game", "captain__profile")
    if game_slug:
        teams = teams.filter(game__slug=game_slug)
    return teams


def get_team_with_roster(team_id: int) -> Team | None:
    """The team with its active members (and their profiles) prefetched as ``roster``."""
    roster = active_memberships().select_related("user__profile").order_by("joined_at")
    return (
        list_teams()
        .prefetch_related(Prefetch("memberships", queryset=roster, to_attr="roster"))
        .filter(pk=team_id)
        .first()
    )
