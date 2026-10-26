from django import forms
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from apps.accounts.exceptions import NicknameTakenError
from apps.accounts.models import Profile, User
from apps.accounts.selectors import is_nickname_taken
from apps.accounts.validators import NICKNAME_MAX_LENGTH, nickname_validator
from apps.games.models import Game
from apps.games.regions import HEARTHSTONE_REGIONS, STEAM_GAMES, WILDRIFT_REGIONS


class SignupForm(forms.Form):
    """Extra signup fields, mixed into allauth's signup form and headless signup input."""

    nickname = forms.CharField(
        label=_("Nickname"), max_length=NICKNAME_MAX_LENGTH, validators=[nickname_validator]
    )

    def clean_nickname(self) -> str:
        nickname: str = self.cleaned_data["nickname"]
        if is_nickname_taken(nickname):
            raise forms.ValidationError(str(NicknameTakenError()))
        return nickname

    def signup(self, request: HttpRequest, user: User) -> None:
        # The profile is created together with the user in AccountAdapter.save_user.
        pass


class ProfileForm(forms.ModelForm[Profile]):
    class Meta:
        model = Profile
        fields = ("nickname", "avatar", "country", "timezone", "bio")
        widgets = {"avatar": forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"})}

    def clean_nickname(self) -> str:
        # Report the case-insensitive uniqueness on the field, not as a form-wide error.
        nickname: str = self.cleaned_data["nickname"]
        if is_nickname_taken(nickname, exclude_profile_id=self.instance.pk):
            raise forms.ValidationError(str(NicknameTakenError()))
        return nickname


class GameAccountForm(forms.Form):
    game = forms.ModelChoiceField(
        label=_("Game"),
        queryset=Game.objects.filter(is_active=True).exclude(slug__in=STEAM_GAMES),
        to_field_name="slug",
    )
    external_id = forms.CharField(label=_("Riot ID or BattleTag"), max_length=64)
    region = forms.ChoiceField(
        label=_("Region"),
        choices=[(r.value, r.label) for r in (*WILDRIFT_REGIONS, *HEARTHSTONE_REGIONS)],
    )
