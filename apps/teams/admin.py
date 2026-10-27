from django.contrib import admin

from apps.teams.models import Team, TeamInvite, TeamMembership


class TeamMembershipInline(admin.TabularInline[TeamMembership, Team]):
    model = TeamMembership
    extra = 0
    fields = ("user", "role", "joined_at", "left_at")
    readonly_fields = ("user", "role", "joined_at", "left_at")
    can_delete = False

    def has_add_permission(self, request: object, obj: object = None) -> bool:
        # Rosters change through team services (invites, transfers), not the admin.
        return False


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin[Team]):
    list_display = ("name", "tag", "game", "captain", "created_at")
    list_filter = ("game",)
    search_fields = ("name", "tag", "captain__email", "captain__profile__nickname")
    list_select_related = ("game", "captain")
    readonly_fields = ("game", "captain", "created_at", "updated_at")
    inlines = (TeamMembershipInline,)


@admin.register(TeamInvite)
class TeamInviteAdmin(admin.ModelAdmin[TeamInvite]):
    list_display = ("team", "invitee", "role", "status", "created_at", "expires_at")
    list_filter = ("status", "role")
    list_select_related = ("team", "invitee")
    # Invites change state through services only.
    readonly_fields = [f.name for f in TeamInvite._meta.fields]

    def has_add_permission(self, request: object) -> bool:
        return False
