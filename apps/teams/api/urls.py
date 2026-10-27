from django.urls import path

from apps.teams.api.views import (
    InviteAcceptView,
    InviteDeclineView,
    InviteDetailView,
    MyInviteListView,
    TeamDetailView,
    TeamInviteListView,
    TeamInviteRevokeView,
    TeamListView,
)

app_name = "teams-api"

urlpatterns = [
    path("teams/", TeamListView.as_view(), name="team-list"),
    path("teams/<int:pk>/", TeamDetailView.as_view(), name="team-detail"),
    path("teams/<int:pk>/invites/", TeamInviteListView.as_view(), name="team-invites"),
    path(
        "teams/<int:pk>/invites/<int:invite_id>/",
        TeamInviteRevokeView.as_view(),
        name="team-invite-revoke",
    ),
    path("me/invites/", MyInviteListView.as_view(), name="my-invites"),
    path("invites/<str:token>/", InviteDetailView.as_view(), name="invite-detail"),
    path("invites/<str:token>/accept/", InviteAcceptView.as_view(), name="invite-accept"),
    path("invites/<str:token>/decline/", InviteDeclineView.as_view(), name="invite-decline"),
]
