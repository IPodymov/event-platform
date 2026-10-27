import threading

import pytest
from django.db import IntegrityError, connection
from django.test import Client
from django.urls import reverse
from rest_framework.test import APIClient

from apps.games import services
from apps.games.exceptions import InvalidMapPoolError, MapPoolNotSupportedError
from apps.games.models import GameSlug, MapPool
from apps.games.tests.factories import seeded_game

pytestmark = pytest.mark.django_db

MAPS = ["Mirage", "Inferno", "Nuke", "Ancient", "Anubis", "Dust2", "Train"]


def make_pool(name: str = "Active Duty", maps: list[str] = MAPS) -> MapPool:
    return services.map_pool_save(game=seeded_game(GameSlug.CS2), name=name, maps=maps)


def test_save_strips_names() -> None:
    pool = make_pool(maps=[f" {m} " for m in MAPS])

    assert pool.maps == MAPS
    assert not pool.is_active


@pytest.mark.parametrize(
    "maps",
    [MAPS[:6], [*MAPS, "Vertigo"], [*MAPS[:6], "mirage"], [*MAPS[:6], "  "]],
    ids=["six", "eight", "duplicate", "blank"],
)
def test_save_requires_seven_distinct_maps(maps: list[str]) -> None:
    with pytest.raises(InvalidMapPoolError):
        make_pool(maps=maps)


@pytest.mark.parametrize("slug", [GameSlug.DOTA2, GameSlug.WILDRIFT, GameSlug.HEARTHSTONE])
def test_only_cs2_has_map_pools(slug: GameSlug) -> None:
    with pytest.raises(MapPoolNotSupportedError):
        services.map_pool_save(game=seeded_game(slug), name="x", maps=MAPS)


def test_activate_switches_active_pool() -> None:
    old = services.map_pool_activate(pool=make_pool("Old"))
    new = make_pool("New")

    services.map_pool_activate(pool=new)

    old.refresh_from_db()
    assert not old.is_active
    assert MapPool.objects.get(is_active=True) == new


def test_database_allows_one_active_pool_per_game() -> None:
    services.map_pool_activate(pool=make_pool("A"))

    with pytest.raises(IntegrityError):
        MapPool.objects.create(game=seeded_game(GameSlug.CS2), name="B", maps=MAPS, is_active=True)


def test_database_rejects_incomplete_active_pool() -> None:
    with pytest.raises(IntegrityError):
        MapPool.objects.create(
            game=seeded_game(GameSlug.CS2), name="B", maps=MAPS[:3], is_active=True
        )


@pytest.mark.django_db(transaction=True)
def test_concurrent_activation_leaves_one_active_pool() -> None:
    pools = [make_pool(f"Pool {i}") for i in range(4)]
    errors: list[BaseException] = []

    def activate(pool: MapPool) -> None:
        try:
            services.map_pool_activate(pool=pool)
        except BaseException as error:
            errors.append(error)
        finally:
            connection.close()

    threads = [threading.Thread(target=activate, args=(p,)) for p in pools]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert MapPool.objects.filter(is_active=True).count() == 1


def test_api_returns_active_pool(api_client: APIClient) -> None:
    services.map_pool_activate(pool=make_pool())

    response = api_client.get("/api/v1/games/cs2/map-pool/")

    assert response.status_code == 200
    assert response.json() == {"name": "Active Duty", "maps": MAPS}


def test_api_404_without_active_pool(api_client: APIClient) -> None:
    make_pool()

    assert api_client.get("/api/v1/games/cs2/map-pool/").status_code == 404


def test_admin_creates_and_activates_pool(admin_client: Client) -> None:
    response = admin_client.post(
        reverse("admin:games_mappool_add"),
        {"game": seeded_game(GameSlug.CS2).pk, "name": "Season 1", "maps": ",".join(MAPS)},
    )
    assert response.status_code == 302
    pool = MapPool.objects.get(name="Season 1")

    admin_client.post(
        reverse("admin:games_mappool_changelist"),
        {"action": "activate", "_selected_action": [pool.pk]},
    )

    pool.refresh_from_db()
    assert pool.is_active


def test_admin_rejects_invalid_maps(admin_client: Client) -> None:
    response = admin_client.post(
        reverse("admin:games_mappool_add"),
        {"game": seeded_game(GameSlug.CS2).pk, "name": "Bad", "maps": "Mirage,Mirage"},
    )

    assert response.status_code == 200
    assert response.context["adminform"].form.errors["maps"]
