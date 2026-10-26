from django.contrib import admin

from apps.games.models import Game


@admin.register(Game)
class GameAdmin(admin.ModelAdmin[Game]):
    list_display = (
        "name",
        "slug",
        "participant_type",
        "roster_size",
        "max_substitutes",
        "is_active",
    )
    list_filter = ("participant_type", "is_active")
