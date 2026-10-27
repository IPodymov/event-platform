from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

TEAM_NAME_MAX_LENGTH = 32

tag_validator = RegexValidator(
    regex=r"^[A-Za-z0-9]{2,5}$",
    message=_("Tag must be 2 to 5 Latin letters or digits."),
    code="invalid_tag",
)


class Team(models.Model):
    name = models.CharField(_("name"), max_length=TEAM_NAME_MAX_LENGTH)
    tag = models.CharField(_("tag"), max_length=5, validators=[tag_validator])
    logo = models.ImageField(_("logo"), upload_to="team_logos/", blank=True)
    game = models.ForeignKey(
        "games.Game", on_delete=models.PROTECT, related_name="teams", verbose_name=_("game")
    )
    captain = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="captained_teams",
        verbose_name=_("captain"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("team")
        verbose_name_plural = _("teams")
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                "game",
                Lower("name"),
                name="teams_team_name_ci_unique_per_game",
                violation_error_message=_("A team with this name already exists."),
            ),
            models.UniqueConstraint(
                "game",
                Lower("tag"),
                name="teams_team_tag_ci_unique_per_game",
                violation_error_message=_("A team with this tag already exists."),
            ),
        ]

    def __str__(self) -> str:
        return f"[{self.tag}] {self.name}"


class TeamRole(models.TextChoices):
    CAPTAIN = "captain", _("Captain")
    PLAYER = "player", _("Player")
    SUBSTITUTE = "substitute", _("Substitute")


class TeamMembership(models.Model):
    """A player's stay in a team; ``left_at`` is set when they leave."""

    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="memberships", verbose_name=_("team")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships",
        verbose_name=_("user"),
    )
    # Copy of team.game so the database can enforce one active team per discipline.
    game = models.ForeignKey(
        "games.Game", on_delete=models.PROTECT, related_name="+", verbose_name=_("game")
    )
    role = models.CharField(_("role"), max_length=20, choices=TeamRole.choices)
    joined_at = models.DateTimeField(_("joined at"), auto_now_add=True)
    left_at = models.DateTimeField(_("left at"), null=True, blank=True)

    class Meta:
        verbose_name = _("team membership")
        verbose_name_plural = _("team memberships")
        ordering = ("joined_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("user", "game"),
                condition=Q(left_at__isnull=True),
                name="teams_membership_one_active_team_per_game",
                violation_error_message=_("The player is already in a team of this game."),
            ),
            models.UniqueConstraint(
                fields=("team",),
                condition=Q(left_at__isnull=True, role="captain"),
                name="teams_membership_one_active_captain",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} in {self.team_id} ({self.role})"

    @property
    def is_active(self) -> bool:
        return self.left_at is None


# Roles a player can be invited to; the captain role is only transferred.
INVITE_ROLES = [
    (TeamRole.PLAYER.value, TeamRole.PLAYER.label),
    (TeamRole.SUBSTITUTE.value, TeamRole.SUBSTITUTE.label),
]


class InviteStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    ACCEPTED = "accepted", _("Accepted")
    DECLINED = "declined", _("Declined")
    REVOKED = "revoked", _("Revoked")


class TeamInvite(models.Model):
    """An invitation to a team: personal (``invitee`` set) or a shareable link."""

    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="invites", verbose_name=_("team")
    )
    invitee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="team_invites",
        verbose_name=_("invitee"),
    )
    token = models.CharField(_("token"), max_length=64, unique=True)
    role = models.CharField(
        _("role"),
        max_length=20,
        choices=INVITE_ROLES,
        default=TeamRole.PLAYER,
    )
    status = models.CharField(
        _("status"), max_length=20, choices=InviteStatus.choices, default=InviteStatus.PENDING
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("created by"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(_("expires at"))
    responded_at = models.DateTimeField(_("responded at"), null=True, blank=True)

    class Meta:
        verbose_name = _("team invite")
        verbose_name_plural = _("team invites")
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("team", "invitee"),
                condition=Q(status="pending", invitee__isnull=False),
                name="teams_invite_one_pending_per_invitee",
            ),
        ]

    def __str__(self) -> str:
        return f"Invite to {self.team_id} ({self.status})"

    @property
    def is_link(self) -> bool:
        return self.invitee_id is None
