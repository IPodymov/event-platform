from django.utils.translation import gettext_lazy as _
from django_stubs_ext import StrOrPromise

from config.exceptions import DomainError, DomainPermissionError


class TournamentsError(DomainError):
    """Base class for domain errors of the tournaments app."""

    message: StrOrPromise = _("Tournament operation failed.")


class EmailNotVerifiedError(DomainPermissionError):
    message = _("Confirm your email address to organize tournaments.")


class NotTournamentManagerError(DomainPermissionError):
    message = _("Only the tournament organizer can do this.")


class GameNotAvailableError(TournamentsError):
    message = _("This discipline is not available.")
    field = "game"


class InvalidRegionError(TournamentsError):
    message = _("This region is not available for the discipline.")
    field = "region"


class InvalidSeriesFormatError(TournamentsError):
    message = _("This series format is not allowed for the discipline.")
    field = "series_format"


class InvalidScheduleError(TournamentsError):
    message = _("Check the tournament dates.")


class RegistrationMustOpenBeforeCloseError(InvalidScheduleError):
    message = _("Registration must open before it closes.")
    field = "registration_closes_at"


class CheckinBeforeRegistrationClosesError(InvalidScheduleError):
    message = _("Check-in cannot open before registration closes.")
    field = "checkin_opens_at"


class CheckinMustOpenBeforeStartError(InvalidScheduleError):
    message = _("Check-in must open before the tournament starts.")
    field = "checkin_opens_at"


class RegistrationClosesInPastError(InvalidScheduleError):
    message = _("Registration must close in the future.")
    field = "registration_closes_at"


class InvalidStatusTransitionError(TournamentsError):
    message = _("The tournament cannot move to this status.")
    field = "status"


class AlreadyPublishedError(TournamentsError):
    message = _("The tournament is already published.")


class TournamentLockedError(TournamentsError):
    message = _("These settings can no longer be changed.")
