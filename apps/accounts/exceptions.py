from django.utils.translation import gettext_lazy as _
from django_stubs_ext import StrOrPromise

from config.exceptions import DomainError


class AccountsError(DomainError):
    """Base class for domain errors of the accounts app."""

    message: StrOrPromise = _("Account operation failed.")


class SocialAccountAlreadyLinkedError(AccountsError):
    message = _("Another account of this provider is already linked. Unlink it first.")


class SocialSignupNotAllowedError(AccountsError):
    message = _(
        "This account is not linked to any profile. Sign in with email and link it "
        "in your account settings."
    )


class NicknameTakenError(AccountsError):
    message = _("This nickname is already taken.")
    field = "nickname"


class InvalidAvatarError(AccountsError):
    message = _("Upload a JPEG, PNG or WebP image.")
    field = "avatar"


class AvatarTooLargeError(InvalidAvatarError):
    message = _("The image is too large.")


class GameAccountTakenError(AccountsError):
    message = _("This account is already linked to another player.")
    field = "external_id"


class GameAccountExistsError(AccountsError):
    message = _("You already have an account for this game.")
    field = "game"


class SteamGameAccountError(AccountsError):
    message = _("Accounts for Steam games come from your linked Steam account.")
    field = "game"


class InvalidExternalIdError(AccountsError):
    field = "external_id"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidRegionError(AccountsError):
    message = _("Choose a region of this game.")
    field = "region"


class VerificationNotAllowedError(AccountsError):
    message = _("Only staff can verify game accounts.")
