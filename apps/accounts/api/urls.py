from django.urls import path

from apps.accounts.api.views import MyProfileView

app_name = "accounts-api"

urlpatterns = [
    path("me/profile/", MyProfileView.as_view(), name="my-profile"),
]
