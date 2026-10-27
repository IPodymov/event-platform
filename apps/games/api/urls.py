from django.urls import path

from apps.games.api.views import ActiveMapPoolView, GameListView

app_name = "games-api"

urlpatterns = [
    path("games/", GameListView.as_view(), name="game-list"),
    path("games/<slug:slug>/map-pool/", ActiveMapPoolView.as_view(), name="map-pool"),
]
