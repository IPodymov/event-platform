from typing import Any

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts import services
from apps.accounts.api.serializers import ProfileSerializer
from apps.accounts.models import Profile


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
