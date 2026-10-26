from django.contrib import admin
from django.contrib.admin.options import InlineModelAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Profile, User


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
