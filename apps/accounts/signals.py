from typing import Any

from allauth.socialaccount.models import SocialLogin
from allauth.socialaccount.signals import (
    social_account_added,
    social_account_removed,
    social_account_updated,
)
from django.dispatch import receiver
from django.http import HttpRequest

from apps.accounts.game_accounts import sync_steam_game_accounts
from apps.accounts.selectors import STEAM_PROVIDER


@receiver(social_account_added)
@receiver(social_account_updated)
def steam_linked(request: HttpRequest, sociallogin: SocialLogin, **kwargs: Any) -> None:
    if sociallogin.account.provider == STEAM_PROVIDER:
        sync_steam_game_accounts(user=sociallogin.user)


@receiver(social_account_removed)
def steam_unlinked(request: HttpRequest, socialaccount: Any, **kwargs: Any) -> None:
    if socialaccount.provider == STEAM_PROVIDER:
        sync_steam_game_accounts(user=socialaccount.user)
