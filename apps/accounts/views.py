from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import UpdateView

from apps.accounts import services
from apps.accounts.exceptions import AccountsError
from apps.accounts.forms import ProfileForm
from apps.accounts.models import Profile


class ProfileEditView(LoginRequiredMixin, UpdateView[Profile, ProfileForm]):
    form_class = ProfileForm
    template_name = "accounts/profile_edit.html"
    success_url = reverse_lazy("accounts:profile_edit")

    def get_object(self, queryset: Any = None) -> Profile:
        return get_object_or_404(Profile, user=self.request.user)

    def form_valid(self, form: ProfileForm) -> HttpResponse:
        data = {field: form.cleaned_data[field] for field in services.PROFILE_EDITABLE_FIELDS}
        try:
            # ModelForm has already written the input into form.instance; start from the DB row.
            services.profile_update(
                profile=self.get_object(), data=data, avatar=self.request.FILES.get("avatar")
            )
        except AccountsError as error:
            form.add_error(error.field, str(error))
            return self.form_invalid(form)
        messages.success(self.request, _("Profile saved."))
        return redirect(self.get_success_url())
