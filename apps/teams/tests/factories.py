import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import UserFactory
from apps.games.models import Game, GameSlug
from apps.teams.models import Team, TeamMembership, TeamRole


class TeamFactory(DjangoModelFactory[Team]):
    """A team with its captain's membership."""

    class Meta:
        model = Team
        skip_postgeneration_save = True

    name = factory.Sequence(lambda n: f"Team {n}")
    tag = factory.Sequence(lambda n: f"T{n}")
    game = factory.LazyFunction(lambda: Game.objects.get(slug=GameSlug.CS2))
    captain = factory.SubFactory(UserFactory)
    captain_membership = factory.RelatedFactory(
        "apps.teams.tests.factories.TeamMembershipFactory",
        factory_related_name="team",
        user=factory.SelfAttribute("..captain"),
        role=TeamRole.CAPTAIN,
    )


class TeamMembershipFactory(DjangoModelFactory[TeamMembership]):
    class Meta:
        model = TeamMembership

    team = factory.SubFactory(TeamFactory)
    user = factory.SubFactory(UserFactory)
    game = factory.SelfAttribute("team.game")
    role = TeamRole.PLAYER
