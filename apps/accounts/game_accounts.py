"""Services for players' game accounts (SteamID64, Riot ID, BattleTag)."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.exceptions import (
    GameAccountExistsError,
    GameAccountTakenError,
    InvalidExternalIdError,
    InvalidRegionError,
    SteamGameAccountError,
    VerificationNotAllowedError,
)
from apps.accounts.models import GameAccount, User
from apps.accounts.selectors import get_steam_id, is_external_id_taken
from apps.accounts.validators import battletag_validator, riot_id_validator
from apps.games.models import Game
from apps.games.regions import ACCOUNT_REGIONS, EXTERNAL_ID_KIND, STEAM_GAMES, ExternalIdKind

_MANUAL_ID_VALIDATORS = {
    ExternalIdKind.RIOT_ID: riot_id_validator,
    ExternalIdKind.BATTLETAG: battletag_validator,
}


def _clean_manual_account(game: Game, external_id: str, region: str) -> str:
    if game.slug in STEAM_GAMES:
        raise SteamGameAccountError
    external_id = external_id.strip()
    try:
        _MANUAL_ID_VALIDATORS[EXTERNAL_ID_KIND[game.slug]](external_id)
    except ValidationError as error:
        raise InvalidExternalIdError(error.messages[0]) from error
    if region not in ACCOUNT_REGIONS[game.slug]:
        raise InvalidRegionError
    return external_id


def _save(account: GameAccount) -> GameAccount:
    try:
        with transaction.atomic():
            account.save()
    except IntegrityError as error:
        raise GameAccountTakenError from error
    return account


def game_account_link(*, user: User, game: Game, external_id: str, region: str) -> GameAccount:
    """Add a manually entered account (Riot ID, BattleTag); it awaits verification."""
    external_id = _clean_manual_account(game, external_id, region)
    if GameAccount.objects.filter(user=user, game=game).exists():
        raise GameAccountExistsError
    if is_external_id_taken(game.pk, external_id):
        raise GameAccountTakenError
    return _save(GameAccount(user=user, game=game, external_id=external_id, region=region))


def game_account_update(*, account: GameAccount, external_id: str, region: str) -> GameAccount:
    """Change a manual account; a changed id has to be verified again."""
    external_id = _clean_manual_account(account.game, external_id, region)
    if is_external_id_taken(account.game_id, external_id, exclude_account_id=account.pk):
        raise GameAccountTakenError
    if external_id.casefold() != account.external_id.casefold():
        account.verified, account.verified_by, account.verified_at = False, None, None
    account.external_id, account.region = external_id, region
    return _save(account)


def game_account_delete(*, account: GameAccount) -> None:
    # TODO(Sprint 3): forbid while the account is in an active tournament roster.
    if account.game.slug in STEAM_GAMES:
        raise SteamGameAccountError
    account.delete()


def sync_steam_game_accounts(*, user: User) -> None:
    """Mirror the linked Steam account into verified CS2 and Dota 2 game accounts."""
    steam_id = get_steam_id(user)
    with transaction.atomic():
        if steam_id is None:
            GameAccount.objects.filter(user=user, game__slug__in=STEAM_GAMES).delete()
            return
        for game in Game.objects.filter(slug__in=STEAM_GAMES):
            GameAccount.objects.update_or_create(
                user=user,
                game=game,
                defaults={
                    "external_id": steam_id,
                    "region": "",
                    # Proven by Steam OpenID, so no moderator check is needed.
                    "verified": True,
                    "verified_by": None,
                    "verified_at": timezone.now(),
                },
            )


def game_account_set_verified(*, account: GameAccount, moderator: User, verified: bool) -> None:
    # TODO(Sprint 9): check the moderator role and write the decision to AuditLog.
    if not moderator.is_staff:
        raise VerificationNotAllowedError
    account.verified = verified
    account.verified_by = moderator if verified else None
    account.verified_at = timezone.now() if verified else None
    account.save(update_fields=["verified", "verified_by", "verified_at", "updated_at"])
