from typing import cast

from django.contrib import admin
from django.contrib.admin.options import InlineModelAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from apps.accounts import game_accounts
from apps.accounts.models import GameAccount, Profile, User


class UserCreationForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email",)


class UserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


class ProfileInline(admin.StackedInline[Profile, User]):
    model = Profile
    can_delete = False
    fields = ("nickname", "avatar", "country", "timezone", "bio")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    form = UserEditForm
    add_form = UserCreationForm
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name")}),
        (
            _("Permissions"),
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "usable_password", "password1", "password2"),
            },
        ),
    )
    list_display = ("email", "profile__nickname", "is_staff", "is_active")
    search_fields = ("email", "profile__nickname")
    list_select_related = ("profile",)
    ordering = ("email",)

    def get_inlines(self, request: HttpRequest, obj: User | None) -> list[type[InlineModelAdmin]]:
        # The add form only asks for credentials; the profile is edited afterwards.
        return list(self.inlines) if obj is not None else []


@admin.register(GameAccount)
class GameAccountAdmin(admin.ModelAdmin[GameAccount]):
    list_display = (
        "external_id",
        "game",
        "region",
        "user",
        "verified",
        "verified_by",
        "verified_at",
    )
    list_filter = ("verified", "game", "region")
    search_fields = ("external_id", "user__email", "user__profile__nickname")
    list_select_related = ("game", "user", "verified_by")
    readonly_fields = ("verified", "verified_by", "verified_at", "created_at", "updated_at")
    actions = ("verify", "unverify")

    def has_add_permission(self, request: HttpRequest) -> bool:
        # Accounts are added by players (or synced from Steam), never by staff.
        return False

    @admin.action(description=_("Verify selected game accounts"))
    def verify(self, request: HttpRequest, queryset: QuerySet[GameAccount]) -> None:
        self._set_verified(request, queryset, verified=True)

    @admin.action(description=_("Remove verification"))
    def unverify(self, request: HttpRequest, queryset: QuerySet[GameAccount]) -> None:
        self._set_verified(request, queryset, verified=False)

    def _set_verified(
        self, request: HttpRequest, queryset: QuerySet[GameAccount], *, verified: bool
    ) -> None:
        moderator = cast(User, request.user)
        for account in queryset:
            game_accounts.game_account_set_verified(
                account=account, moderator=moderator, verified=verified
            )
        self.message_user(request, _("Updated: %(count)d") % {"count": queryset.count()})
