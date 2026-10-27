from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _

from apps.games.models import SeriesFormat
from apps.games.regions import Region

TOURNAMENT_TITLE_MAX_LENGTH = 100
MIN_PARTICIPANTS = 2
MAX_PARTICIPANTS = 256


class TournamentStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    REGISTRATION_OPEN = "registration_open", _("Registration open")
    REGISTRATION_CLOSED = "registration_closed", _("Registration closed")
    CHECKIN = "checkin", _("Check-in")
    IN_PROGRESS = "in_progress", _("In progress")
    COMPLETED = "completed", _("Completed")
    CANCELLED = "cancelled", _("Cancelled")


class StageFormat(models.TextChoices):
    SINGLE_ELIM = "single_elim", _("Single elimination")
    DOUBLE_ELIM = "double_elim", _("Double elimination")
    ROUND_ROBIN = "round_robin", _("Round robin")
    SWISS = "swiss", _("Swiss")


class Tournament(models.Model):
    game = models.ForeignKey(
        "games.Game", on_delete=models.PROTECT, related_name="tournaments", verbose_name=_("game")
    )
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organized_tournaments",
        verbose_name=_("organizer"),
    )
    title = models.CharField(_("title"), max_length=TOURNAMENT_TITLE_MAX_LENGTH)
    rules = models.TextField(_("rules"), blank=True)
    region = models.CharField(_("region"), max_length=20, choices=Region.choices)
    max_participants = models.PositiveSmallIntegerField(
        _("max participants"),
        validators=[MinValueValidator(MIN_PARTICIPANTS), MaxValueValidator(MAX_PARTICIPANTS)],
    )
    # Default series length of the tournament's matches.
    series_format = models.PositiveSmallIntegerField(
        _("series format"), choices=SeriesFormat.choices
    )
    registration_opens_at = models.DateTimeField(_("registration opens at"))
    registration_closes_at = models.DateTimeField(_("registration closes at"))
    checkin_opens_at = models.DateTimeField(_("check-in opens at"))
    starts_at = models.DateTimeField(_("starts at"))
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=TournamentStatus.choices,
        default=TournamentStatus.DRAFT,
        db_index=True,
    )
    # Drafts are private until published; a published draft opens registration on schedule.
    published_at = models.DateTimeField(_("published at"), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("tournament")
        verbose_name_plural = _("tournaments")
        ordering = ("starts_at", "pk")
        constraints = [
            models.CheckConstraint(
                condition=Q(max_participants__gte=MIN_PARTICIPANTS)
                & Q(max_participants__lte=MAX_PARTICIPANTS),
                name="tournaments_tournament_max_participants_range",
            ),
            models.CheckConstraint(
                condition=Q(registration_opens_at__lt=F("registration_closes_at"))
                & Q(registration_closes_at__lte=F("checkin_opens_at"))
                & Q(checkin_opens_at__lt=F("starts_at")),
                name="tournaments_tournament_schedule_order",
            ),
            models.CheckConstraint(
                condition=Q(status__in=[TournamentStatus.DRAFT, TournamentStatus.CANCELLED])
                | Q(published_at__isnull=False),
                name="tournaments_tournament_published_after_draft",
            ),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def is_published(self) -> bool:
        return self.published_at is not None


class Stage(models.Model):
    """A phase of a tournament (e.g. groups, then playoffs) with its bracket format."""

    tournament = models.ForeignKey(
        Tournament, on_delete=models.CASCADE, related_name="stages", verbose_name=_("tournament")
    )
    order = models.PositiveSmallIntegerField(_("order"))
    format = models.CharField(_("format"), max_length=20, choices=StageFormat.choices)
    # Format options (group size, advancing count, finals Bo...), validated by bracket generators.
    settings = models.JSONField(_("settings"), default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("stage")
        verbose_name_plural = _("stages")
        ordering = ("tournament", "order")
        constraints = [
            models.UniqueConstraint(
                fields=("tournament", "order"), name="tournaments_stage_unique_order"
            ),
            models.CheckConstraint(condition=Q(order__gte=1), name="tournaments_stage_order_gte_1"),
        ]

    def __str__(self) -> str:
        return f"{self.tournament} #{self.order}"
