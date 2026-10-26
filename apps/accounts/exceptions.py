from django.utils.translation import gettext_lazy as _

from config.exceptions import DomainError


class AccountsError(DomainError):
    """Base class for domain errors of the accounts app."""

    message = _("Account operation failed.")


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
