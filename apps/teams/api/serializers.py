from rest_framework import serializers

from apps.games.models import Game
from apps.teams.models import Team, TeamMembership


class TeamMemberSerializer(serializers.ModelSerializer[TeamMembership]):
    nickname = serializers.CharField(source="user.profile.nickname", read_only=True)

    class Meta:
        model = TeamMembership
        fields = ("nickname", "role", "joined_at")
        read_only_fields = fields


class TeamSerializer(serializers.ModelSerializer[Team]):
    game: serializers.SlugRelatedField[Game] = serializers.SlugRelatedField(
        slug_field="slug", queryset=Game.objects.filter(is_active=True)
    )
    captain = serializers.CharField(source="captain.profile.nickname", read_only=True)

    class Meta:
        model = Team
        fields: tuple[str, ...] = ("id", "name", "tag", "logo", "game", "captain", "created_at")
        read_only_fields: tuple[str, ...] = ("id", "captain", "created_at")
        extra_kwargs = {"logo": {"required": False}}
        # Uniqueness is checked by the service, which reports the right field.
        validators: list[object] = []


class TeamDetailSerializer(TeamSerializer):
    roster = TeamMemberSerializer(many=True, read_only=True)

    class Meta(TeamSerializer.Meta):
        fields = (*TeamSerializer.Meta.fields, "roster")
        read_only_fields = fields
