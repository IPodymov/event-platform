from typing import Any, ClassVar

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField

from apps.accounts.validators import NICKNAME_MAX_LENGTH, nickname_validator, validate_timezone
from apps.games.regions import Region

DEFAULT_TIMEZONE = "Europe/Moscow"


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    @classmethod
    def normalize_email(cls, email: str | None) -> str:
        # Emails are compared case-insensitively, so they are stored lowercased.
        return (email or "").strip().lower()

    def get_by_natural_key(self, username: str | None) -> "User":
        return self.get(email=self.normalize_email(username))

    def _create_user(self, email: str, password: str | None, **extra_fields: Any) -> "User":
        if not email:
            raise ValueError("The email must be set.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> "User":
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields["is_staff"] is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields["is_superuser"] is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None  # type: ignore[assignment]
    email = models.EmailField(_("email address"), unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects: ClassVar[UserManager] = UserManager()  # type: ignore[assignment]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
        ]

    def __str__(self) -> str:
        return self.email


class Profile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="profile", verbose_name=_("user")
    )
    nickname = models.CharField(
        _("nickname"), max_length=NICKNAME_MAX_LENGTH, validators=[nickname_validator]
    )
    avatar = models.ImageField(_("avatar"), upload_to="avatars/", blank=True)
    country = CountryField(_("country"), blank=True)
    timezone = models.CharField(
        _("time zone"), max_length=64, default=DEFAULT_TIMEZONE, validators=[validate_timezone]
    )
    bio = models.TextField(_("about"), max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("profile")
        verbose_name_plural = _("profiles")
        constraints = [
            models.UniqueConstraint(
                Lower("nickname"),
                name="accounts_profile_nickname_ci_unique",
                violation_error_message=_("This nickname is already taken."),
            ),
        ]

    def __str__(self) -> str:
        return self.nickname


class GameAccount(models.Model):
    """A player's account in a discipline: SteamID64, Riot ID or BattleTag."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="game_accounts", verbose_name=_("user")
    )
    game = models.ForeignKey(
        "games.Game", on_delete=models.PROTECT, related_name="accounts", verbose_name=_("game")
    )
    external_id = models.CharField(_("account id"), max_length=64)
    region = models.CharField(_("region"), max_length=20, choices=Region.choices, blank=True)
    verified = models.BooleanField(_("verified"), default=False)
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("verified by"),
    )
    verified_at = models.DateTimeField(_("verified at"), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("game account")
        verbose_name_plural = _("game accounts")
        ordering = ("game__name",)
        constraints = [
            models.UniqueConstraint(
                "game",
                Lower("external_id"),
                name="accounts_gameaccount_game_external_id_ci_unique",
                violation_error_message=_("This account is already linked to another player."),
            ),
            models.UniqueConstraint(
                fields=("user", "game"),
                name="accounts_gameaccount_one_per_game",
                violation_error_message=_("You already have an account for this game."),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.game_id}: {self.external_id}"
