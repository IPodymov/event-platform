from django.db import transaction

from apps.games.exceptions import InvalidMapPoolError, MapPoolNotSupportedError
from apps.games.models import MAP_POOL_GAMES, MAP_POOL_SIZE, Game, MapPool


def clean_maps(maps: list[str]) -> list[str]:
    """Strip names and require exactly MAP_POOL_SIZE non-empty, case-insensitively unique maps."""
    cleaned = [name.strip() for name in maps]
    if (
        len(cleaned) != MAP_POOL_SIZE
        or not all(cleaned)
        or len({name.casefold() for name in cleaned}) != len(cleaned)
    ):
        raise InvalidMapPoolError
    return cleaned


def map_pool_save(
    *, game: Game, name: str, maps: list[str], pool: MapPool | None = None
) -> MapPool:
    """Create or update a map pool. Maps of the active pool can be changed in place."""
    if game.slug not in MAP_POOL_GAMES:
        raise MapPoolNotSupportedError
    pool = pool or MapPool()
    pool.game, pool.name, pool.maps = game, name.strip(), clean_maps(maps)
    pool.save()
    return pool


def map_pool_activate(*, pool: MapPool) -> MapPool:
    """Make ``pool`` the only active pool of its discipline."""
    clean_maps(pool.maps)
    with transaction.atomic():
        # Lock the discipline's pools so concurrent activations cannot both win.
        list(MapPool.objects.select_for_update().filter(game_id=pool.game_id))
        MapPool.objects.filter(game_id=pool.game_id, is_active=True).exclude(pk=pool.pk).update(
            is_active=False
        )
        pool.is_active = True
        pool.save(update_fields=["is_active", "updated_at"])
    return pool
