from apps.accounts.exceptions import SocialAccountAlreadyLinkedError, SocialSignupNotAllowedError
from apps.accounts.models import User
from apps.accounts.selectors import get_social_uid


def validate_social_link(*, user: User, provider: str, uid: str) -> None:
    """Allow linking unless the user already has a different account of ``provider``."""
    linked = get_social_uid(user, provider)
    if linked is not None and linked != uid:
        raise SocialAccountAlreadyLinkedError


def validate_social_login(*, is_linked: bool) -> None:
    """Third-party providers are linked identities only: they never create accounts."""
    if not is_linked:
        raise SocialSignupNotAllowedError
