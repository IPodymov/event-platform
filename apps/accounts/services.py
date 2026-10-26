from apps.accounts.exceptions import SteamAlreadyLinkedError, SteamSignupNotAllowedError
from apps.accounts.models import User
from apps.accounts.selectors import get_steam_id


def validate_steam_link(*, user: User, steam_id: str) -> None:
    """Allow linking ``steam_id`` unless the user already has a different Steam account."""
    linked = get_steam_id(user)
    if linked is not None and linked != steam_id:
        raise SteamAlreadyLinkedError


def validate_steam_login(*, is_linked: bool) -> None:
    """Steam is a linked identity only: it never creates new accounts."""
    if not is_linked:
        raise SteamSignupNotAllowedError
