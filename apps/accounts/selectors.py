from allauth.socialaccount.models import SocialAccount

from apps.accounts.models import User

STEAM_PROVIDER = "steam"
DISCORD_PROVIDER = "discord"


def get_social_uid(user: User, provider: str) -> str | None:
    """Return the user's account id at ``provider`` (one per provider), if linked."""
    return (
        SocialAccount.objects.filter(user=user, provider=provider)
        .values_list("uid", flat=True)
        .first()
    )


def get_steam_id(user: User) -> str | None:
    """Return the SteamID64 linked to the user, if any."""
    return get_social_uid(user, STEAM_PROVIDER)


def get_discord_id(user: User) -> str | None:
    """Return the Discord user id linked to the user, if any."""
    return get_social_uid(user, DISCORD_PROVIDER)
