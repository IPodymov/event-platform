from django.db.models import QuerySet

from apps.games.models import Game


def list_active_games() -> QuerySet[Game]:
    return Game.objects.filter(is_active=True)
