from typing import Any, cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.views.generic import FormView

from apps.accounts.models import User
from apps.teams import services
from apps.teams.exceptions import TeamsError
from apps.teams.forms import TeamCreateForm, TeamInviteForm
from apps.teams.models import Team, TeamInvite
from apps.teams.selectors import (
    get_invite_by_token,
    get_team_with_roster,
    list_team_invites,
    list_user_invites,
)
from config.exceptions import DomainError


class TeamCreateView(LoginRequiredMixin, FormView[TeamCreateForm]):
    form_class = TeamCreateForm
    template_name = "teams/team_create.html"

    def form_valid(self, form: TeamCreateForm) -> HttpResponse:
        try:
            team = services.team_create(user=cast(User, self.request.user), **form.cleaned_data)
        except TeamsError as error:
            form.add_error(error.field, str(error))
            return self.form_invalid(form)
        messages.success(self.request, _("Team created."))
        return redirect("teams:detail", pk=team.pk)


def team_detail(request: HttpRequest, pk: int) -> HttpResponse:
    team = get_team_with_roster(pk)
    if team is None:
        raise Http404
    context: dict[str, Any] = {"team": team}
    if request.user.is_authenticated and team.captain_id == request.user.pk:
        context["invite_form"] = TeamInviteForm()
        context["invites"] = list_team_invites(team)
    return render(request, "teams/team_detail.html", context)


@login_required
@require_POST
def team_invite_create(request: HttpRequest, pk: int) -> HttpResponse:
    team = get_object_or_404(Team.objects.select_related("game"), pk=pk)
    form = TeamInviteForm(request.POST)
    if form.is_valid():
        try:
            services.invite_create(by=cast(User, request.user), team=team, **form.cleaned_data)
            messages.success(request, _("Invitation created."))
        except DomainError as error:
            messages.error(request, str(error))
    return redirect("teams:detail", pk=pk)


@login_required
@require_POST
def team_invite_revoke(request: HttpRequest, pk: int, invite_id: int) -> HttpResponse:
    invite = get_object_or_404(TeamInvite.objects.select_related("team"), pk=invite_id, team_id=pk)
    try:
        services.invite_revoke(by=cast(User, request.user), invite=invite)
    except DomainError as error:
        messages.error(request, str(error))
    return redirect("teams:detail", pk=pk)


@login_required
def invite_detail(request: HttpRequest, token: str) -> HttpResponse:
    invite = get_invite_by_token(token)
    if invite is None:
        raise Http404
    if request.method == "POST":
        user = cast(User, request.user)
        try:
            if request.POST.get("action") == "decline":
                services.invite_decline(user=user, invite=invite)
                messages.info(request, _("Invitation declined."))
                return redirect("teams:my_invites")
            services.invite_accept(user=user, invite=invite)
        except DomainError as error:
            messages.error(request, str(error))
            return redirect("teams:invite", token=token)
        messages.success(request, _("You joined the team."))
        return redirect("teams:detail", pk=invite.team_id)
    return render(request, "teams/invite_detail.html", {"invite": invite})


@login_required
def my_invites(request: HttpRequest) -> HttpResponse:
    invites = list_user_invites(cast(User, request.user))
    return render(request, "teams/my_invites.html", {"invites": invites})
