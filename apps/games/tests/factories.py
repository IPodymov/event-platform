import factory
from factory.django import DjangoModelFactory

from apps.games.models import Game, GameSlug, ParticipantType, ResultVerification, SeriesFormat


def seeded_game(slug: GameSlug) -> Game:
    """Disciplines are seeded by a data migration, so tests reuse them."""
    return Game.objects.get(slug=slug)


class GameFactory(DjangoModelFactory[Game]):
    """An extra discipline outside the seeded catalog."""

    class Meta:
        model = Game

    slug = factory.Sequence(lambda n: f"game{n}")
    name = factory.Sequence(lambda n: f"Game {n}")
    participant_type = ParticipantType.TEAM
    roster_size = 5
    max_substitutes = 2
    allowed_series = factory.LazyFunction(
        lambda: [SeriesFormat.BO1, SeriesFormat.BO3, SeriesFormat.BO5]
    )
    result_verification = ResultVerification.MANUAL


class SoloGameFactory(GameFactory):
    participant_type = ParticipantType.SOLO
    roster_size = 1
    max_substitutes = 0
