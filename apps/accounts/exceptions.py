from django.utils.translation import gettext_lazy as _


class AccountsError(Exception):
    """Base class for domain errors of the accounts app."""

    message = _("Account operation failed.")

    def __str__(self) -> str:
        return str(self.message)


class SteamAlreadyLinkedError(AccountsError):
    message = _("Another Steam account is already linked. Unlink it first.")


class SteamSignupNotAllowedError(AccountsError):
    message = _(
        "This Steam account is not linked to any profile. Sign in with email "
        "and link Steam in your account settings."
    )
