from typing import cast

from django.db.models import QuerySet
from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.serializers import BaseSerializer

from apps.accounts.models import User
from apps.teams import services
from apps.teams.api.serializers import TeamDetailSerializer, TeamSerializer
from apps.teams.models import Team
from apps.teams.selectors import get_team_with_roster, list_teams


@extend_schema_view(
    get=extend_schema(
        tags=["teams"],
        parameters=[OpenApiParameter("game", str, description="Discipline slug")],
    ),
    post=extend_schema(tags=["teams"], description="Create a team; you become its captain."),
)
class TeamListView(generics.ListCreateAPIView[Team]):
    serializer_class = TeamSerializer
    permission_classes = (IsAuthenticatedOrReadOnly,)
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get_queryset(self) -> QuerySet[Team]:
        return list_teams(game_slug=self.request.query_params.get("game"))

    def perform_create(self, serializer: BaseSerializer[Team]) -> None:
        serializer.instance = services.team_create(
            user=cast(User, self.request.user), **serializer.validated_data
        )


@extend_schema(tags=["teams"])
class TeamDetailView(generics.RetrieveAPIView[Team]):
    """A team with its active roster."""

    serializer_class = TeamDetailSerializer
    permission_classes = (AllowAny,)

    def get_object(self) -> Team:
        team = get_team_with_roster(self.kwargs["pk"])
        if team is None:
            raise Http404
        return team
