from django.utils.translation import gettext_lazy as _
from django_stubs_ext import StrOrPromise

from config.exceptions import DomainError


class GamesError(DomainError):
    """Base class for domain errors of the games app."""

    message: StrOrPromise = _("Game operation failed.")


class MapPoolNotSupportedError(GamesError):
    message = _("This discipline has no map veto.")
    field = "game"


class InvalidMapPoolError(GamesError):
    message = _("A map pool needs exactly 7 different maps.")
    field = "maps"
