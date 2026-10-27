from django.utils.translation import gettext_lazy as _
from django_stubs_ext import StrOrPromise

from config.exceptions import DomainError


class TeamsError(DomainError):
    """Base class for domain errors of the teams app."""

    message: StrOrPromise = _("Team operation failed.")


class NotATeamGameError(TeamsError):
    message = _("Teams can only be created in team disciplines.")
    field = "game"


class AlreadyInTeamError(TeamsError):
    message = _("You are already in a team of this game.")
    field = "game"


class TeamNameTakenError(TeamsError):
    message = _("A team with this name already exists.")
    field = "name"


class TeamTagTakenError(TeamsError):
    message = _("A team with this tag already exists.")
    field = "tag"


class InvalidLogoError(TeamsError):
    message = _("Upload a JPEG, PNG or WebP image.")
    field = "logo"


class LogoTooLargeError(InvalidLogoError):
    message = _("The image is too large.")
