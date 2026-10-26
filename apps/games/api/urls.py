from django.urls import path

from apps.games.api.views import GameListView

app_name = "games-api"

urlpatterns = [
    path("games/", GameListView.as_view(), name="game-list"),
]
