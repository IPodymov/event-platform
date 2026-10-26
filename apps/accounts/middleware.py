import zoneinfo
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from django.utils import timezone


class UserTimezoneMiddleware:
    """Render datetimes in the time zone from the signed-in user's profile."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        profile = getattr(request.user, "profile", None) if request.user.is_authenticated else None
        if profile is not None:
            timezone.activate(zoneinfo.ZoneInfo(profile.timezone))
        else:
            timezone.deactivate()
        return self.get_response(request)
