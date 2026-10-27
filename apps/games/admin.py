from typing import Any

from django import forms
from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from apps.games import services
from apps.games.exceptions import GamesError
from apps.games.models import Game, MapPool


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


class MapPoolForm(forms.ModelForm[MapPool]):
    class Meta:
        model = MapPool
        fields = ("game", "name", "maps")
        help_texts = {"maps": _("Exactly 7 maps, separated by commas.")}

    def clean_maps(self) -> list[str]:
        try:
            return services.clean_maps(self.cleaned_data["maps"])
        except GamesError as error:
            raise forms.ValidationError(str(error)) from error


@admin.register(MapPool)
class MapPoolAdmin(admin.ModelAdmin[MapPool]):
    form = MapPoolForm
    list_display = ("name", "game", "maps", "is_active", "updated_at")
    list_filter = ("game", "is_active")
    readonly_fields = ("is_active",)
    actions = ("activate",)

    def save_model(self, request: HttpRequest, obj: MapPool, form: Any, change: bool) -> None:
        services.map_pool_save(game=obj.game, name=obj.name, maps=obj.maps, pool=obj)

    @admin.action(description=_("Make the selected pool active"))
    def activate(self, request: HttpRequest, queryset: QuerySet[MapPool]) -> None:
        if queryset.count() != 1:
            self.message_user(request, _("Select exactly one pool."), messages.ERROR)
            return
        try:
            services.map_pool_activate(pool=queryset.get())
        except GamesError as error:
            self.message_user(request, str(error), messages.ERROR)
            return
        self.message_user(request, _("The pool is now active."))
