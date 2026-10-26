from typing import Any

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialLogin
from django.contrib import messages
from django.http import HttpRequest
from django.shortcuts import redirect

from apps.accounts import services
from apps.accounts.exceptions import AccountsError, SteamAlreadyLinkedError
from apps.accounts.models import User
from apps.accounts.selectors import STEAM_PROVIDER


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest, sociallogin: SocialLogin) -> bool:
        # Accounts are created with email only; third-party providers can just be linked.
        return False

    def pre_social_login(self, request: HttpRequest, sociallogin: SocialLogin) -> None:
        if sociallogin.account.provider != STEAM_PROVIDER:
            return
        try:
            # allauth only starts the "connect" process for authenticated users.
            if sociallogin.state.get("process") == "connect" and isinstance(request.user, User):
                services.validate_steam_link(user=request.user, steam_id=sociallogin.account.uid)
            else:
                services.validate_steam_login(is_linked=sociallogin.is_existing)
        except AccountsError as error:
            messages.error(request, str(error))
            target = (
                "socialaccount_connections"
                if isinstance(error, SteamAlreadyLinkedError)
                else "account_login"
            )
            raise ImmediateHttpResponse(redirect(target)) from error

    def populate_user(self, request: HttpRequest, sociallogin: SocialLogin, data: Any) -> Any:
        # The custom User has no username; Steam persona names stay in extra_data.
        data = {k: v for k, v in data.items() if k != "username"}
        return super().populate_user(request, sociallogin, data)
