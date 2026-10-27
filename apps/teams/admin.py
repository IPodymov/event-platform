from django.contrib import admin

from apps.teams.models import Team, TeamMembership


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
