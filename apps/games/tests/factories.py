import factory
from factory.django import DjangoModelFactory

from apps.games.models import Game, GameSlug, ParticipantType, ResultVerification, SeriesFormat


class GameFactory(DjangoModelFactory[Game]):
    class Meta:
        model = Game
        django_get_or_create = ("slug",)

    slug = GameSlug.CS2
    name = factory.LazyAttribute(lambda o: GameSlug(o.slug).label)
    participant_type = ParticipantType.TEAM
    roster_size = 5
    max_substitutes = 2
    allowed_series = factory.LazyFunction(
        lambda: [SeriesFormat.BO1, SeriesFormat.BO3, SeriesFormat.BO5]
    )
    result_verification = ResultVerification.MANUAL


class SoloGameFactory(GameFactory):
    slug = GameSlug.HEARTHSTONE
    participant_type = ParticipantType.SOLO
    roster_size = 1
    max_substitutes = 0
    allowed_series = factory.LazyFunction(lambda: [SeriesFormat.BO3, SeriesFormat.BO5])
