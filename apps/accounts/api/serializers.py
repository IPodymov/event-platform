from django_countries.serializer_fields import CountryField
from rest_framework import serializers

from apps.accounts.models import Profile


class ProfileSerializer(serializers.ModelSerializer[Profile]):
    country = CountryField(required=False, allow_blank=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Profile
        fields = ("nickname", "email", "avatar", "country", "timezone", "bio")
        extra_kwargs = {"avatar": {"required": False}}
