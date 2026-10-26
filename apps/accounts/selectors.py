from allauth.socialaccount.models import SocialAccount
from django.db.models import QuerySet

from apps.accounts.models import GameAccount, Profile, User

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


def is_nickname_taken(nickname: str, *, exclude_profile_id: int | None = None) -> bool:
    profiles = Profile.objects.filter(nickname__iexact=nickname)
    if exclude_profile_id is not None:
        profiles = profiles.exclude(pk=exclude_profile_id)
    return profiles.exists()


def list_game_accounts(user: User) -> QuerySet[GameAccount]:
    return GameAccount.objects.filter(user=user).select_related("game")


def is_external_id_taken(
    game_id: int, external_id: str, *, exclude_account_id: int | None = None
) -> bool:
    accounts = GameAccount.objects.filter(game_id=game_id, external_id__iexact=external_id)
    if exclude_account_id is not None:
        accounts = accounts.exclude(pk=exclude_account_id)
    return accounts.exists()
