from typing import cast

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView

from apps.accounts.models import User
from apps.teams import services
from apps.teams.exceptions import TeamsError
from apps.teams.forms import TeamCreateForm
from apps.teams.selectors import get_team_with_roster


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
    return render(request, "teams/team_detail.html", {"team": team})
