from allauth.socialaccount.models import SocialAccount

from apps.accounts.models import User

STEAM_PROVIDER = "steam"


def get_steam_id(user: User) -> str | None:
    """Return the SteamID64 linked to the user, if any."""
    return (
        SocialAccount.objects.filter(user=user, provider=STEAM_PROVIDER)
        .values_list("uid", flat=True)
        .first()
    )
