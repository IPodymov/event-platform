from typing import Any

from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, views
from rest_framework.response import Response


class DomainError(Exception):
    """Base class for business rule violations raised by services.

    ``field`` names the input the error belongs to, if any, so API and form layers
    can attach it to that field.
    """

    message = _("Operation failed.")
    field: str | None = None

    def __str__(self) -> str:
        return str(self.message)


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """Render domain errors as 400 validation errors."""
    if isinstance(exc, DomainError):
        detail = {exc.field: [str(exc)]} if exc.field else [str(exc)]
        exc = exceptions.ValidationError(detail)
    return views.exception_handler(exc, context)
