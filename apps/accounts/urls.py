from django.urls import path

from apps.accounts.views import ProfileEditView

app_name = "accounts"

urlpatterns = [
    path("profile/", ProfileEditView.as_view(), name="profile_edit"),
]
