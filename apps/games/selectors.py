from django.db.models import QuerySet

from apps.games.models import Game, MapPool


def list_active_games() -> QuerySet[Game]:
    return Game.objects.filter(is_active=True)


def get_active_map_pool(game_slug: str) -> MapPool | None:
    return MapPool.objects.filter(game__slug=game_slug, is_active=True).first()
