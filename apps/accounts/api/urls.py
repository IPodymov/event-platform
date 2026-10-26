from django.urls import path

from apps.accounts.api.views import MyGameAccountDetailView, MyGameAccountListView, MyProfileView

app_name = "accounts-api"

urlpatterns = [
    path("me/profile/", MyProfileView.as_view(), name="my-profile"),
    path("me/game-accounts/", MyGameAccountListView.as_view(), name="my-game-accounts"),
    path(
        "me/game-accounts/<int:pk>/",
        MyGameAccountDetailView.as_view(),
        name="my-game-account",
    ),
]
