from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers

from apps.games.models import Game
from apps.games.regions import ACCOUNT_REGIONS, EXTERNAL_ID_KIND, TOURNAMENT_REGIONS, Region

REGION_LIST_SCHEMA = inline_serializer(
    "Region", {"value": serializers.CharField(), "label": serializers.CharField()}, many=True
)


def _regions(regions: tuple[Region, ...]) -> list[dict[str, str]]:
    return [{"value": r.value, "label": str(r.label)} for r in regions]


class GameSerializer(serializers.ModelSerializer[Game]):
    external_id_kind = serializers.SerializerMethodField()
    account_regions = serializers.SerializerMethodField()
    tournament_regions = serializers.SerializerMethodField()

    def get_external_id_kind(self, game: Game) -> str:
        return EXTERNAL_ID_KIND.get(game.slug, "")

    @extend_schema_field(REGION_LIST_SCHEMA)
    def get_account_regions(self, game: Game) -> list[dict[str, str]]:
        return _regions(ACCOUNT_REGIONS.get(game.slug, ()))

    @extend_schema_field(REGION_LIST_SCHEMA)
    def get_tournament_regions(self, game: Game) -> list[dict[str, str]]:
        return _regions(TOURNAMENT_REGIONS.get(game.slug, ()))

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
            "external_id_kind",
            "account_regions",
            "tournament_regions",
        )
        read_only_fields = fields
