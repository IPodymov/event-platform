from typing import Any, cast

from django.db.models import QuerySet
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.accounts import game_accounts, services
from apps.accounts.api.serializers import (
    GameAccountSerializer,
    GameAccountUpdateSerializer,
    ProfileSerializer,
    PublicProfileSerializer,
)
from apps.accounts.models import GameAccount, Profile, User
from apps.accounts.selectors import get_public_profile, list_game_accounts


@extend_schema(tags=["profile"])
class MyProfileView(generics.RetrieveUpdateAPIView[Profile]):
    """The signed-in user's own profile. Send ``avatar`` as multipart to replace it."""

    serializer_class = ProfileSerializer
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self) -> Profile:
        return get_object_or_404(Profile, user=self.request.user)

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        profile = self.get_object()
        serializer = self.get_serializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = {
            k: v
            for k, v in serializer.validated_data.items()
            if k in services.PROFILE_EDITABLE_FIELDS
        }
        profile = services.profile_update(
            profile=profile, data=data, avatar=serializer.validated_data.get("avatar")
        )
        return Response(self.get_serializer(profile).data)


@extend_schema(tags=["game accounts"])
class MyGameAccountListView(generics.ListCreateAPIView[GameAccount]):
    """The signed-in user's game accounts. Steam games are filled from the linked Steam."""

    serializer_class = GameAccountSerializer
    pagination_class = None

    def get_queryset(self) -> QuerySet[GameAccount]:
        return list_game_accounts(cast(User, self.request.user))

    def perform_create(self, serializer: BaseSerializer[GameAccount]) -> None:
        serializer.instance = game_accounts.game_account_link(
            user=cast(User, self.request.user), **serializer.validated_data
        )


@extend_schema(tags=["game accounts"])
class MyGameAccountDetailView(generics.RetrieveUpdateDestroyAPIView[GameAccount]):
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self) -> QuerySet[GameAccount]:
        return list_game_accounts(cast(User, self.request.user))

    def get_serializer_class(self) -> type[BaseSerializer[GameAccount]]:
        if self.request.method == "PATCH":
            return GameAccountUpdateSerializer
        return GameAccountSerializer

    @extend_schema(request=GameAccountUpdateSerializer, responses=GameAccountSerializer)
    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        account = self.get_object()
        serializer = GameAccountUpdateSerializer(account, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        account = game_accounts.game_account_update(
            account=account,
            external_id=serializer.validated_data.get("external_id", account.external_id),
            region=serializer.validated_data.get("region", account.region),
        )
        return Response(GameAccountSerializer(account).data)

    def perform_destroy(self, instance: GameAccount) -> None:
        game_accounts.game_account_delete(account=instance)


@extend_schema(tags=["players"])
class PublicProfileView(generics.RetrieveAPIView[Profile]):
    """A player's public profile by nickname (case-insensitive)."""

    serializer_class = PublicProfileSerializer
    permission_classes = (AllowAny,)
    lookup_url_kwarg = "nickname"

    def get_object(self) -> Profile:
        profile = get_public_profile(self.kwargs["nickname"])
        if profile is None:
            raise Http404
        return profile
