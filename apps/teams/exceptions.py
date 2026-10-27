from django.utils.translation import gettext_lazy as _
from django_stubs_ext import StrOrPromise

from config.exceptions import DomainError, DomainPermissionError


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


class NotTeamCaptainError(DomainPermissionError):
    message = _("Only the team captain can do this.")


class NotInviteeError(DomainPermissionError):
    message = _("This invitation is addressed to another player.")


class PlayerNotFoundError(TeamsError):
    message = _("No player with this nickname.")
    field = "nickname"


class AlreadyInvitedError(TeamsError):
    message = _("This player already has a pending invitation to the team.")
    field = "nickname"


class AlreadyMemberError(TeamsError):
    message = _("This player is already in the team.")
    field = "nickname"


class InviteNotActiveError(TeamsError):
    message = _("This invitation is no longer valid.")


class RosterFullError(TeamsError):
    message = _("The team has no free slot for this role.")
    field = "role"
