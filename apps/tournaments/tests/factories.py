from datetime import timedelta

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import UserFactory
from apps.games.models import Game, GameSlug, SeriesFormat
from apps.games.regions import Region
from apps.tournaments.models import Stage, StageFormat, Tournament


def _in_days(days: float) -> factory.LazyFunction:
    return factory.LazyFunction(lambda: timezone.now() + timedelta(days=days))


class TournamentFactory(DjangoModelFactory[Tournament]):
    """An unpublished CS2 draft scheduled a week ahead, with one stage."""

    class Meta:
        model = Tournament
        skip_postgeneration_save = True

    game = factory.LazyFunction(lambda: Game.objects.get(slug=GameSlug.CS2))
    organizer = factory.SubFactory(UserFactory)
    title = factory.Sequence(lambda n: f"Cup {n}")
    region = Region.EU
    max_participants = 16
    series_format = SeriesFormat.BO1
    registration_opens_at = _in_days(1)
    registration_closes_at = _in_days(5)
    checkin_opens_at = _in_days(6)
    starts_at = _in_days(7)
    stage = factory.RelatedFactory(
        "apps.tournaments.tests.factories.StageFactory", factory_related_name="tournament"
    )


class StageFactory(DjangoModelFactory[Stage]):
    class Meta:
        model = Stage

    tournament = factory.SubFactory(TournamentFactory, stage=None)
    order = 1
    format = StageFormat.SINGLE_ELIM
