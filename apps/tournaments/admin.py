from django.contrib import admin

from apps.tournaments.models import Stage, Tournament


class StageInline(admin.TabularInline[Stage, Tournament]):
    model = Stage
    extra = 0
    fields = ("order", "format", "settings")
    readonly_fields = ("order", "format")


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin[Tournament]):
    list_display = ("title", "game", "organizer", "region", "status", "starts_at", "published_at")
    list_filter = ("status", "game", "region")
    search_fields = ("title", "organizer__email", "organizer__profile__nickname")
    list_select_related = ("game", "organizer")
    date_hierarchy = "starts_at"
    # Lifecycle changes go through services (publish, cancel, schedule tasks).
    readonly_fields = ("organizer", "game", "status", "published_at", "created_at", "updated_at")
    inlines = (StageInline,)

    def has_add_permission(self, request: object) -> bool:
        return False
