from django.urls import path

from apps.teams import views

app_name = "teams"

urlpatterns = [
    path("teams/new/", views.TeamCreateView.as_view(), name="create"),
    path("teams/<int:pk>/", views.team_detail, name="detail"),
    path("teams/<int:pk>/invites/", views.team_invite_create, name="invite_create"),
    path(
        "teams/<int:pk>/invites/<int:invite_id>/revoke/",
        views.team_invite_revoke,
        name="invite_revoke",
    ),
    path(
        "teams/<int:pk>/members/<int:membership_id>/",
        views.team_member_action,
        name="member_action",
    ),
    path("teams/<int:pk>/leave/", views.team_leave, name="leave"),
    path("invites/<str:token>/", views.invite_detail, name="invite"),
    path("profile/invites/", views.my_invites, name="my_invites"),
]
