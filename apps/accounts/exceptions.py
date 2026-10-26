from django.utils.translation import gettext_lazy as _


class AccountsError(Exception):
    """Base class for domain errors of the accounts app."""

    message = _("Account operation failed.")

    def __str__(self) -> str:
        return str(self.message)


class SocialAccountAlreadyLinkedError(AccountsError):
    message = _("Another account of this provider is already linked. Unlink it first.")


class SocialSignupNotAllowedError(AccountsError):
    message = _(
        "This account is not linked to any profile. Sign in with email and link it "
        "in your account settings."
    )
