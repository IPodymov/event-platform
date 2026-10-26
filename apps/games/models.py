from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _


class GameSlug(models.TextChoices):
    CS2 = "cs2", "Counter-Strike 2"
    DOTA2 = "dota2", "Dota 2"
    WILDRIFT = "wildrift", "League of Legends: Wild Rift"
    HEARTHSTONE = "hearthstone", "Hearthstone"


class ParticipantType(models.TextChoices):
    SOLO = "solo", _("Solo")
    TEAM = "team", _("Team")


class SeriesFormat(models.IntegerChoices):
    BO1 = 1, "Bo1"
    BO3 = 3, "Bo3"
    BO5 = 5, "Bo5"


class ResultVerification(models.TextChoices):
    MANUAL = "manual", _("Manual confirmation")
    OPENDOTA = "opendota", _("OpenDota")


class Game(models.Model):
    name = models.CharField(_("name"), max_length=100)
    slug = models.SlugField(_("slug"), choices=GameSlug.choices, unique=True)
    participant_type = models.CharField(
        _("participant type"), max_length=10, choices=ParticipantType.choices
    )
    roster_size = models.PositiveSmallIntegerField(_("roster size"))
    max_substitutes = models.PositiveSmallIntegerField(_("max substitutes"), default=0)
    allowed_series = ArrayField(
        models.PositiveSmallIntegerField(choices=SeriesFormat.choices),
        verbose_name=_("allowed series"),
    )
    result_verification = models.CharField(
        _("result verification"),
        max_length=20,
        choices=ResultVerification.choices,
        default=ResultVerification.MANUAL,
    )
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("game")
        verbose_name_plural = _("games")
        ordering = ("name",)
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(participant_type=ParticipantType.SOLO, roster_size=1, max_substitutes=0)
                    | Q(participant_type=ParticipantType.TEAM, roster_size__gte=2)
                ),
                name="games_game_roster_matches_participant_type",
            ),
            models.CheckConstraint(
                condition=Q(allowed_series__len__gt=0)
                & Q(allowed_series__contained_by=[f.value for f in SeriesFormat]),
                name="games_game_allowed_series_valid",
            ),
            models.CheckConstraint(
                condition=~Q(max_substitutes__gt=F("roster_size")),
                name="games_game_substitutes_not_above_roster",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def is_team(self) -> bool:
        return self.participant_type == ParticipantType.TEAM
