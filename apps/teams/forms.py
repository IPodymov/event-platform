from django import forms
from django.utils.translation import gettext_lazy as _

from apps.games.models import Game, ParticipantType
from apps.teams.models import INVITE_ROLES, TEAM_NAME_MAX_LENGTH, TeamRole, tag_validator


class TeamCreateForm(forms.Form):
    game = forms.ModelChoiceField(
        label=_("Game"),
        queryset=Game.objects.filter(is_active=True, participant_type=ParticipantType.TEAM),
        to_field_name="slug",
    )
    name = forms.CharField(label=_("Name"), max_length=TEAM_NAME_MAX_LENGTH)
    tag = forms.CharField(label=_("Tag"), max_length=5, validators=[tag_validator])
    logo = forms.ImageField(
        label=_("Logo"),
        required=False,
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )


class TeamInviteForm(forms.Form):
    nickname = forms.CharField(
        label=_("Player nickname"),
        required=False,
        help_text=_("Leave empty to create a shareable link."),
    )
    role = forms.ChoiceField(
        label=_("Role"),
        choices=INVITE_ROLES,
        initial=TeamRole.PLAYER,
    )
