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


# Riot ID: game name (3-16 chars) + "#" + tag line (3-5 letters/digits).
riot_id_validator = RegexValidator(
    regex=r"^[^#\s][^#]{1,14}[^#\s]#[A-Za-z0-9]{3,5}$",
    message=_("Enter a Riot ID in the form Name#TAG."),
    code="invalid_riot_id",
)

# BattleTag: name (3-12 letters/digits, not starting with a digit) + "#" + 4-6 digits.
battletag_validator = RegexValidator(
    regex=r"^[^\W\d_][^\W_]{2,11}#\d{4,6}$",
    message=_("Enter a BattleTag in the form Name#1234."),
    code="invalid_battletag",
)

steam_id64_validator = RegexValidator(
    regex=r"^7656119\d{10}$",
    message=_("Enter a valid SteamID64."),
    code="invalid_steam_id64",
)
