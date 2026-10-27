from django.urls import path

from apps.teams.views import TeamCreateView, team_detail

app_name = "teams"

urlpatterns = [
    path("teams/new/", TeamCreateView.as_view(), name="create"),
    path("teams/<int:pk>/", team_detail, name="detail"),
]
