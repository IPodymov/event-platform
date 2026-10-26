from typing import Any

from django_countries.serializer_fields import CountryField
from rest_framework import serializers

from apps.accounts.models import GameAccount, Profile
from apps.games.models import Game


class ProfileSerializer(serializers.ModelSerializer[Profile]):
    country = CountryField(required=False, allow_blank=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Profile
        fields = ("nickname", "email", "avatar", "country", "timezone", "bio")
        extra_kwargs = {"avatar": {"required": False}}


class GameAccountSerializer(serializers.ModelSerializer[GameAccount]):
    game = serializers.SlugRelatedField(
        slug_field="slug", queryset=Game.objects.filter(is_active=True)
    )

    class Meta:
        model = GameAccount
        fields = ("id", "game", "external_id", "region", "verified")
        read_only_fields = ("id", "verified")
        # Uniqueness is enforced by the service, which reports it on the right field.
        validators: list[Any] = []


class GameAccountUpdateSerializer(serializers.ModelSerializer[GameAccount]):
    class Meta:
        model = GameAccount
        fields = ("external_id", "region")
