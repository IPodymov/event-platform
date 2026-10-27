from typing import Any, cast

from django.db.models import QuerySet
from django.http import Http404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.tournaments import services
from apps.tournaments.api.serializers import TournamentSerializer
from apps.tournaments.models import Tournament
from apps.tournaments.selectors import (
    get_visible_tournament,
    list_organized_tournaments,
    list_published_tournaments,
)


@extend_schema_view(
    get=extend_schema(tags=["tournaments"], description="Published tournaments."),
    post=extend_schema(
        tags=["tournaments"],
        description="Create an unpublished draft; requires a verified email.",
    ),
)
class TournamentListView(generics.ListCreateAPIView[Tournament]):
    serializer_class = TournamentSerializer
    permission_classes = (IsAuthenticatedOrReadOnly,)

    def get_queryset(self) -> QuerySet[Tournament]:
        return list_published_tournaments()

    def perform_create(self, serializer: BaseSerializer[Tournament]) -> None:
        serializer.instance = services.tournament_create(
            organizer=cast(User, self.request.user), **serializer.validated_data
        )


@extend_schema_view(
    get=extend_schema(tags=["tournaments"]),
    patch=extend_schema(
        tags=["tournaments"],
        description="Organizer only. Drafts are fully editable; after publishing only "
        "title and rules.",
    ),
)
class TournamentDetailView(generics.RetrieveUpdateAPIView[Tournament]):
    serializer_class = TournamentSerializer
    permission_classes = (IsAuthenticatedOrReadOnly,)
    http_method_names = ("get", "patch", "head", "options")

    def get_object(self) -> Tournament:
        tournament = get_visible_tournament(self.kwargs["pk"], self.request.user)
        if tournament is None:
            raise Http404
        return tournament

    def perform_update(self, serializer: BaseSerializer[Tournament]) -> None:
        tournament = services.tournament_update(
            by=cast(User, self.request.user),
            tournament=cast(Tournament, serializer.instance),
            data=serializer.validated_data,
        )
        serializer.instance = _reload(tournament.pk, self.request.user)


def _reload(pk: int, user: Any) -> Tournament:
    tournament = get_visible_tournament(pk, user)
    if tournament is None:
        raise Http404
    return tournament


class _TournamentActionView(APIView):
    def _act(self, request: Request, pk: int) -> Tournament:
        raise NotImplementedError

    @extend_schema(tags=["tournaments"], request=None, responses=TournamentSerializer)
    def post(self, request: Request, pk: int) -> Response:
        tournament = self._act(request, pk)
        data = TournamentSerializer(_reload(tournament.pk, request.user)).data
        return Response(data, status=status.HTTP_200_OK)


class TournamentPublishView(_TournamentActionView):
    """Make a draft public; registration opens at ``registration_opens_at``."""

    def _act(self, request: Request, pk: int) -> Tournament:
        return services.tournament_publish(
            by=cast(User, request.user), tournament=_reload(pk, request.user)
        )


class TournamentCancelView(_TournamentActionView):
    """Cancel the tournament (any status before completion)."""

    def _act(self, request: Request, pk: int) -> Tournament:
        return services.tournament_cancel(
            by=cast(User, request.user), tournament=_reload(pk, request.user)
        )


@extend_schema(tags=["tournaments"])
class MyTournamentListView(generics.ListAPIView[Tournament]):
    """Tournaments organized by the signed-in user, drafts included."""

    serializer_class = TournamentSerializer
    pagination_class = None

    def get_queryset(self) -> QuerySet[Tournament]:
        return list_organized_tournaments(cast(User, self.request.user))
