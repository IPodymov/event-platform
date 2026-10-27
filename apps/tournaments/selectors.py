from django.contrib.auth.models import AnonymousUser
from django.db.models import Q, QuerySet

from apps.accounts.models import User
from apps.tournaments.models import Tournament


def can_manage_tournament(user: User | AnonymousUser, tournament: Tournament) -> bool:
    # Co-organizers and platform roles arrive with "Роли и права" (Sprint 9); staff act as admins.
    return user.is_authenticated and (user.pk == tournament.organizer_id or user.is_staff)


def _tournaments() -> QuerySet[Tournament]:
    return Tournament.objects.select_related("game", "organizer__profile").prefetch_related(
        "stages"
    )


def list_published_tournaments() -> QuerySet[Tournament]:
    return _tournaments().filter(published_at__isnull=False)


def list_organized_tournaments(user: User) -> QuerySet[Tournament]:
    """All tournaments the user organizes, drafts included, newest first."""
    return _tournaments().filter(organizer=user).order_by("-created_at")


def get_visible_tournament(tournament_id: int, user: User | AnonymousUser) -> Tournament | None:
    """A published tournament, or a draft its organizer (or staff) may see."""
    tournaments = _tournaments().filter(pk=tournament_id)
    if not user.is_staff:
        visible = Q(published_at__isnull=False)
        if user.is_authenticated:
            visible |= Q(organizer=user)
        tournaments = tournaments.filter(visible)
    return tournaments.first()
