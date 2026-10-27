from rest_framework import serializers

from apps.games.models import Game
from apps.tournaments.models import Stage, StageFormat, Tournament


class StageSerializer(serializers.ModelSerializer[Stage]):
    class Meta:
        model = Stage
        fields = ("order", "format", "settings")
        read_only_fields = fields


class TournamentSerializer(serializers.ModelSerializer[Tournament]):
    game: serializers.SlugRelatedField[Game] = serializers.SlugRelatedField(
        slug_field="slug", queryset=Game.objects.filter(is_active=True)
    )
    organizer = serializers.CharField(source="organizer.profile.nickname", read_only=True)
    stage_format = serializers.ChoiceField(
        choices=StageFormat.choices, write_only=True, help_text="Format of the first stage."
    )
    stages = StageSerializer(many=True, read_only=True)

    class Meta:
        model = Tournament
        fields = (
            "id",
            "game",
            "organizer",
            "title",
            "rules",
            "region",
            "max_participants",
            "series_format",
            "registration_opens_at",
            "registration_closes_at",
            "checkin_opens_at",
            "starts_at",
            "status",
            "published_at",
            "stage_format",
            "stages",
            "created_at",
        )
        read_only_fields = ("id", "organizer", "status", "published_at", "stages", "created_at")
        # Cross-field and game-specific rules are checked by the service.
        validators: list[object] = []
