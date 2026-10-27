from django.urls import path

from apps.tournaments.api.views import (
    MyTournamentListView,
    TournamentCancelView,
    TournamentDetailView,
    TournamentListView,
    TournamentPublishView,
)

app_name = "tournaments-api"

urlpatterns = [
    path("tournaments/", TournamentListView.as_view(), name="tournament-list"),
    path("tournaments/<int:pk>/", TournamentDetailView.as_view(), name="tournament-detail"),
    path(
        "tournaments/<int:pk>/publish/", TournamentPublishView.as_view(), name="tournament-publish"
    ),
    path("tournaments/<int:pk>/cancel/", TournamentCancelView.as_view(), name="tournament-cancel"),
    path("me/tournaments/", MyTournamentListView.as_view(), name="my-tournaments"),
]
