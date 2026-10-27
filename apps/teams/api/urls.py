from django.urls import path

from apps.teams.api.views import (
    CaptainTransferView,
    InviteAcceptView,
    InviteDeclineView,
    InviteDetailView,
    MyInviteListView,
    TeamDetailView,
    TeamInviteListView,
    TeamInviteRevokeView,
    TeamLeaveView,
    TeamListView,
    TeamMemberView,
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
    path(
        "teams/<int:pk>/members/<int:membership_id>/",
        TeamMemberView.as_view(),
        name="team-member",
    ),
    path(
        "teams/<int:pk>/transfer-captaincy/",
        CaptainTransferView.as_view(),
        name="team-transfer-captaincy",
    ),
    path("teams/<int:pk>/leave/", TeamLeaveView.as_view(), name="team-leave"),
    path("me/invites/", MyInviteListView.as_view(), name="my-invites"),
    path("invites/<str:token>/", InviteDetailView.as_view(), name="invite-detail"),
    path("invites/<str:token>/accept/", InviteAcceptView.as_view(), name="invite-accept"),
    path("invites/<str:token>/decline/", InviteDeclineView.as_view(), name="invite-decline"),
]
