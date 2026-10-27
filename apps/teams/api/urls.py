from django.urls import path

from apps.teams.api.views import TeamDetailView, TeamListView

app_name = "teams-api"

urlpatterns = [
    path("teams/", TeamListView.as_view(), name="team-list"),
    path("teams/<int:pk>/", TeamDetailView.as_view(), name="team-detail"),
]
