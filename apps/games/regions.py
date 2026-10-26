"""Regions and external account id kinds per discipline."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.games.models import GameSlug


class Region(models.TextChoices):
    # Tournament regions for Steam games (Steam accounts have no region).
    EU = "eu", _("Europe")
    CIS = "cis", _("CIS")
    NA = "na", _("North America")
    SA = "sa", _("South America")
    ASIA = "asia", _("Asia")
    OCE = "oce", _("Oceania")
    # Hearthstone (Battle.net) regions.
    HS_AMERICAS = "hs_americas", _("Americas")
    HS_EUROPE = "hs_europe", _("Europe")
    HS_ASIA_PACIFIC = "hs_apac", _("Asia-Pacific")
    # Wild Rift servers.
    WR_RU = "wr_ru", "RU"
    WR_EUW = "wr_euw", "EUW"
    WR_EUNE = "wr_eune", "EUNE"
    WR_TR = "wr_tr", "TR"


class ExternalIdKind(models.TextChoices):
    STEAM_ID64 = "steam_id64", "Steam ID64"
    RIOT_ID = "riot_id", "Riot ID"
    BATTLETAG = "battletag", "BattleTag"


STEAM_REGIONS = (Region.EU, Region.CIS, Region.NA, Region.SA, Region.ASIA, Region.OCE)
HEARTHSTONE_REGIONS = (Region.HS_AMERICAS, Region.HS_EUROPE, Region.HS_ASIA_PACIFIC)
WILDRIFT_REGIONS = (Region.WR_RU, Region.WR_EUW, Region.WR_EUNE, Region.WR_TR)

EXTERNAL_ID_KIND: dict[str, ExternalIdKind] = {
    GameSlug.CS2: ExternalIdKind.STEAM_ID64,
    GameSlug.DOTA2: ExternalIdKind.STEAM_ID64,
    GameSlug.WILDRIFT: ExternalIdKind.RIOT_ID,
    GameSlug.HEARTHSTONE: ExternalIdKind.BATTLETAG,
}

# Regions a player's game account can belong to; empty means the account has no region.
ACCOUNT_REGIONS: dict[str, tuple[Region, ...]] = {
    GameSlug.CS2: (),
    GameSlug.DOTA2: (),
    GameSlug.WILDRIFT: WILDRIFT_REGIONS,
    GameSlug.HEARTHSTONE: HEARTHSTONE_REGIONS,
}

TOURNAMENT_REGIONS: dict[str, tuple[Region, ...]] = {
    GameSlug.CS2: STEAM_REGIONS,
    GameSlug.DOTA2: STEAM_REGIONS,
    GameSlug.WILDRIFT: WILDRIFT_REGIONS,
    GameSlug.HEARTHSTONE: HEARTHSTONE_REGIONS,
}

STEAM_GAMES = frozenset(slug for slug, kind in EXTERNAL_ID_KIND.items() if kind == "steam_id64")
