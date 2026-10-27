from typing import Any, cast

from django.db.models import QuerySet
from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.teams import services
from apps.teams.api.serializers import (
    TeamDetailSerializer,
    TeamInviteCreateSerializer,
    TeamInviteSerializer,
    TeamMemberSerializer,
    TeamSerializer,
)
from apps.teams.exceptions import NotTeamCaptainError
from apps.teams.models import Team, TeamInvite
from apps.teams.selectors import (
    get_invite_by_token,
    get_team_with_roster,
    list_team_invites,
    list_teams,
    list_user_invites,
)


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


def _team_or_404(pk: int) -> Team:
    team = Team.objects.select_related("game").filter(pk=pk).first()
    if team is None:
        raise Http404
    return team


def _invite_or_404(token: str) -> TeamInvite:
    invite = get_invite_by_token(token)
    if invite is None:
        raise Http404
    return invite


@extend_schema_view(
    get=extend_schema(tags=["team invites"], description="Pending invites (captain only)."),
    post=extend_schema(
        tags=["team invites"],
        request=TeamInviteCreateSerializer,
        responses={201: TeamInviteSerializer},
        description="Invite a player by nickname, or create a link invite without one.",
    ),
)
class TeamInviteListView(generics.ListCreateAPIView[TeamInvite]):
    serializer_class = TeamInviteSerializer
    pagination_class = None

    def get_queryset(self) -> QuerySet[TeamInvite]:
        team = _team_or_404(self.kwargs["pk"])
        if team.captain_id != self.request.user.pk:
            raise NotTeamCaptainError
        return list_team_invites(team).select_related("team__game", "team__captain__profile")

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        data = TeamInviteCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        invite = services.invite_create(
            by=cast(User, request.user), team=_team_or_404(self.kwargs["pk"]), **data.validated_data
        )
        return Response(self.get_serializer(invite).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["team invites"])
class TeamInviteRevokeView(APIView):
    @extend_schema(responses={204: None})
    def delete(self, request: Request, pk: int, invite_id: int) -> Response:
        invite = TeamInvite.objects.select_related("team").filter(pk=invite_id, team_id=pk).first()
        if invite is None:
            raise Http404
        services.invite_revoke(by=cast(User, request.user), invite=invite)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["team invites"])
class MyInviteListView(generics.ListAPIView[TeamInvite]):
    """Personal invitations addressed to the signed-in user."""

    serializer_class = TeamInviteSerializer
    pagination_class = None

    def get_queryset(self) -> QuerySet[TeamInvite]:
        return list_user_invites(cast(User, self.request.user)).select_related(
            "team__captain__profile"
        )


@extend_schema(tags=["team invites"])
class InviteDetailView(generics.RetrieveAPIView[TeamInvite]):
    """An invitation by its token (from a link or a personal invite)."""

    serializer_class = TeamInviteSerializer

    def get_object(self) -> TeamInvite:
        return _invite_or_404(self.kwargs["token"])


@extend_schema(tags=["team invites"])
class InviteAcceptView(APIView):
    @extend_schema(request=None, responses={201: TeamMemberSerializer})
    def post(self, request: Request, token: str) -> Response:
        membership = services.invite_accept(
            user=cast(User, request.user), invite=_invite_or_404(token)
        )
        return Response(TeamMemberSerializer(membership).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["team invites"])
class InviteDeclineView(APIView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request: Request, token: str) -> Response:
        services.invite_decline(user=cast(User, request.user), invite=_invite_or_404(token))
        return Response(status=status.HTTP_204_NO_CONTENT)
