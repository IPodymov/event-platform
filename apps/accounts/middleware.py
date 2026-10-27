import zoneinfo
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from django.utils import timezone

API_PATH_PREFIX = "/api/"


class UserTimezoneMiddleware:
    """Render page datetimes in the time zone from the signed-in user's profile.

    The REST API always answers in UTC; clients convert times themselves.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        profile = None
        if request.user.is_authenticated and not request.path.startswith(API_PATH_PREFIX):
            profile = getattr(request.user, "profile", None)
        if profile is not None:
            timezone.activate(zoneinfo.ZoneInfo(profile.timezone))
        else:
            timezone.deactivate()
        return self.get_response(request)
