from rest_framework import serializers

from apps.games.models import Game


class GameSerializer(serializers.ModelSerializer[Game]):
    class Meta:
        model = Game
        fields = (
            "slug",
            "name",
            "participant_type",
            "roster_size",
            "max_substitutes",
            "allowed_series",
            "result_verification",
        )
        read_only_fields = fields
