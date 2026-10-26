from zoneinfo import available_timezones

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

NICKNAME_MIN_LENGTH = 3
NICKNAME_MAX_LENGTH = 20

nickname_validator = RegexValidator(
    regex=rf"^[A-Za-z0-9_-]{{{NICKNAME_MIN_LENGTH},{NICKNAME_MAX_LENGTH}}}$",
    message=_(
        "Nickname must be 3 to 20 characters long and contain only Latin letters, "
        "digits, underscores and hyphens."
    ),
    code="invalid_nickname",
)


def validate_timezone(value: str) -> None:
    if value not in available_timezones():
        raise ValidationError(_("Unknown time zone."), code="invalid_timezone")
