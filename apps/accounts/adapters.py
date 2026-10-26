from typing import Any

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialLogin
from django.contrib import messages
from django.db import transaction
from django.forms import Form
from django.http import HttpRequest
from django.shortcuts import redirect

from apps.accounts import services
from apps.accounts.exceptions import AccountsError, SocialAccountAlreadyLinkedError
from apps.accounts.models import User


class AccountAdapter(DefaultAccountAdapter):
    def save_user(self, request: HttpRequest, user: User, form: Form, commit: bool = True) -> User:
        # Create the user and the profile atomically, so no user is left without a nickname.
        with transaction.atomic():
            user = super().save_user(request, user, form, commit=commit)
            if commit:
                services.profile_create(user=user, nickname=form.cleaned_data["nickname"])
        return user


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest, sociallogin: SocialLogin) -> bool:
        # Accounts are created with email only; third-party providers can just be linked.
        return False

    def pre_social_login(self, request: HttpRequest, sociallogin: SocialLogin) -> None:
        account = sociallogin.account
        try:
            # allauth only starts the "connect" process for authenticated users.
            if sociallogin.state.get("process") == "connect" and isinstance(request.user, User):
                services.validate_social_link(
                    user=request.user, provider=account.provider, uid=account.uid
                )
            else:
                services.validate_social_login(is_linked=sociallogin.is_existing)
        except AccountsError as error:
            messages.error(request, str(error))
            target = (
                "socialaccount_connections"
                if isinstance(error, SocialAccountAlreadyLinkedError)
                else "account_login"
            )
            raise ImmediateHttpResponse(redirect(target)) from error

    def populate_user(self, request: HttpRequest, sociallogin: SocialLogin, data: Any) -> Any:
        # The custom User has no username; provider nicknames stay in extra_data.
        data = {k: v for k, v in data.items() if k != "username"}
        return super().populate_user(request, sociallogin, data)
