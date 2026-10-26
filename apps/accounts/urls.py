from django.urls import path

from apps.accounts.views import (
    GameAccountDeleteView,
    GameAccountsView,
    ProfileEditView,
    public_profile,
)

app_name = "accounts"

urlpatterns = [
    path("profile/", ProfileEditView.as_view(), name="profile_edit"),
    path("profile/game-accounts/", GameAccountsView.as_view(), name="game_accounts"),
    path(
        "profile/game-accounts/<int:pk>/delete/",
        GameAccountDeleteView.as_view(),
        name="game_account_delete",
    ),
    path("players/<str:nickname>/", public_profile, name="public_profile"),
]
