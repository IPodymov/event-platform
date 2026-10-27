from django.db.models import QuerySet
from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny

from apps.games.api.serializers import GameSerializer, MapPoolSerializer
from apps.games.models import Game, MapPool
from apps.games.selectors import get_active_map_pool, list_active_games


@extend_schema(tags=["games"])
class GameListView(generics.ListAPIView[Game]):
    """Disciplines available for tournaments."""

    serializer_class = GameSerializer
    permission_classes = (AllowAny,)
    pagination_class = None

    def get_queryset(self) -> QuerySet[Game]:
        return list_active_games()


@extend_schema(tags=["games"])
class ActiveMapPoolView(generics.RetrieveAPIView[MapPool]):
    """The discipline's active map pool used for map veto."""

    serializer_class = MapPoolSerializer
    permission_classes = (AllowAny,)

    def get_object(self) -> MapPool:
        pool = get_active_map_pool(self.kwargs["slug"])
        if pool is None:
            raise Http404
        return pool
