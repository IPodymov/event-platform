from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny

from apps.games.api.serializers import GameSerializer
from apps.games.models import Game
from apps.games.selectors import list_active_games


@extend_schema(tags=["games"])
class GameListView(generics.ListAPIView[Game]):
    """Disciplines available for tournaments."""

    serializer_class = GameSerializer
    permission_classes = (AllowAny,)
    pagination_class = None

    def get_queryset(self) -> QuerySet[Game]:
        return list_active_games()
