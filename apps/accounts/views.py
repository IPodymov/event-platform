from typing import Any, cast

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import FormView, UpdateView

from apps.accounts import game_accounts, services
from apps.accounts.exceptions import AccountsError
from apps.accounts.forms import GameAccountForm, ProfileForm
from apps.accounts.models import GameAccount, Profile, User
from apps.accounts.selectors import list_game_accounts


class ProfileEditView(LoginRequiredMixin, UpdateView[Profile, ProfileForm]):
    form_class = ProfileForm
    template_name = "accounts/profile_edit.html"
    success_url = reverse_lazy("accounts:profile_edit")

    def get_object(self, queryset: Any = None) -> Profile:
        return get_object_or_404(Profile, user=self.request.user)

    def form_valid(self, form: ProfileForm) -> HttpResponse:
        data = {field: form.cleaned_data[field] for field in services.PROFILE_EDITABLE_FIELDS}
        try:
            # ModelForm has already written the input into form.instance; start from the DB row.
            services.profile_update(
                profile=self.get_object(), data=data, avatar=self.request.FILES.get("avatar")
            )
        except AccountsError as error:
            form.add_error(error.field, str(error))
            return self.form_invalid(form)
        messages.success(self.request, _("Profile saved."))
        return redirect(self.get_success_url())


class GameAccountsView(LoginRequiredMixin, FormView[GameAccountForm]):
    """Lists the user's game accounts and adds Riot ID / BattleTag accounts."""

    form_class = GameAccountForm
    template_name = "accounts/game_accounts.html"
    success_url = reverse_lazy("accounts:game_accounts")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        kwargs["accounts"] = list_game_accounts(self._user())
        return super().get_context_data(**kwargs)

    def form_valid(self, form: GameAccountForm) -> HttpResponse:
        try:
            game_accounts.game_account_link(user=self._user(), **form.cleaned_data)
        except AccountsError as error:
            form.add_error(error.field, str(error))
            return self.form_invalid(form)
        messages.success(self.request, _("Game account added. It will be verified by a moderator."))
        return super().form_valid(form)

    def _user(self) -> User:
        return cast(User, self.request.user)


class GameAccountDeleteView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        account = get_object_or_404(GameAccount, pk=pk, user=request.user)
        try:
            game_accounts.game_account_delete(account=account)
        except AccountsError as error:
            messages.error(request, str(error))
        return redirect("accounts:game_accounts")
