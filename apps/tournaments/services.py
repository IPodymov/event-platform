from collections.abc import Mapping
from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.selectors import has_verified_email
from apps.games.models import Game
from apps.games.regions import TOURNAMENT_REGIONS
from apps.tournaments.exceptions import (
    AlreadyPublishedError,
    CheckinBeforeRegistrationClosesError,
    CheckinMustOpenBeforeStartError,
    EmailNotVerifiedError,
    GameNotAvailableError,
    InvalidRegionError,
    InvalidSeriesFormatError,
    InvalidStatusTransitionError,
    NotTournamentManagerError,
    RegistrationClosesInPastError,
    RegistrationMustOpenBeforeCloseError,
    TournamentLockedError,
)
from apps.tournaments.models import Stage, StageFormat, Tournament, TournamentStatus
from apps.tournaments.selectors import can_manage_tournament

S = TournamentStatus

# Cancellation is possible from any status before completion (CLAUDE.md §6).
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    S.DRAFT: frozenset({S.REGISTRATION_OPEN, S.CANCELLED}),
    S.REGISTRATION_OPEN: frozenset({S.REGISTRATION_CLOSED, S.CANCELLED}),
    S.REGISTRATION_CLOSED: frozenset({S.CHECKIN, S.CANCELLED}),
    S.CHECKIN: frozenset({S.IN_PROGRESS, S.CANCELLED}),
    S.IN_PROGRESS: frozenset({S.COMPLETED, S.CANCELLED}),
    S.COMPLETED: frozenset(),
    S.CANCELLED: frozenset(),
}

SCHEDULE_FIELDS = (
    "registration_opens_at",
    "registration_closes_at",
    "checkin_opens_at",
    "starts_at",
)
# Fields of a draft; once published only the description can change.
DRAFT_FIELDS = frozenset(
    {"game", "title", "rules", "region", "max_participants", "series_format", "stage_format"}
    | set(SCHEDULE_FIELDS)
)
PUBLISHED_FIELDS = frozenset({"title", "rules"})
FINISHED_STATUSES = frozenset({S.COMPLETED, S.CANCELLED})


def _ensure_can_manage(user: User, tournament: Tournament) -> None:
    if not can_manage_tournament(user, tournament):
        raise NotTournamentManagerError


def _validate_settings(tournament: Tournament) -> None:
    game: Game = tournament.game
    if not game.is_active:
        raise GameNotAvailableError
    if tournament.region not in TOURNAMENT_REGIONS[game.slug]:
        raise InvalidRegionError
    if tournament.series_format not in game.allowed_series:
        raise InvalidSeriesFormatError


def _validate_schedule(tournament: Tournament) -> None:
    opens: datetime = tournament.registration_opens_at
    closes: datetime = tournament.registration_closes_at
    checkin: datetime = tournament.checkin_opens_at
    if opens >= closes:
        raise RegistrationMustOpenBeforeCloseError
    if checkin < closes:
        raise CheckinBeforeRegistrationClosesError
    if checkin >= tournament.starts_at:
        raise CheckinMustOpenBeforeStartError
    if closes <= timezone.now():
        raise RegistrationClosesInPastError


def _validate_draft(tournament: Tournament) -> None:
    _validate_settings(tournament)
    _validate_schedule(tournament)
    # Field-level checks (lengths, participant limits).
    tournament.full_clean(exclude=["organizer", "game"], validate_constraints=False)


def tournament_create(
    *,
    organizer: User,
    game: Game,
    title: str,
    region: str,
    max_participants: int,
    series_format: int,
    registration_opens_at: datetime,
    registration_closes_at: datetime,
    checkin_opens_at: datetime,
    starts_at: datetime,
    stage_format: str,
    rules: str = "",
) -> Tournament:
    """Create an unpublished draft with its first stage."""
    if not has_verified_email(organizer):
        raise EmailNotVerifiedError
    tournament = Tournament(
        organizer=organizer,
        game=game,
        title=title.strip(),
        rules=rules,
        region=region,
        max_participants=max_participants,
        series_format=series_format,
        registration_opens_at=registration_opens_at,
        registration_closes_at=registration_closes_at,
        checkin_opens_at=checkin_opens_at,
        starts_at=starts_at,
    )
    _validate_draft(tournament)
    Stage(order=1, format=stage_format).full_clean(exclude=["tournament"])
    with transaction.atomic():
        tournament.save()
        Stage.objects.create(tournament=tournament, order=1, format=stage_format)
    return tournament


def tournament_update(*, by: User, tournament: Tournament, data: Mapping[str, Any]) -> Tournament:
    """Change a draft freely; after publishing only the title and rules."""
    with transaction.atomic():
        tournament = _lock(tournament.pk)
        _ensure_can_manage(by, tournament)
        if tournament.status in FINISHED_STATUSES:
            raise TournamentLockedError
        editable = DRAFT_FIELDS if not tournament.is_published else PUBLISHED_FIELDS
        if set(data) - editable:
            raise TournamentLockedError

        stage_format = data.get("stage_format")
        for field, value in data.items():
            if field != "stage_format":
                setattr(tournament, field, value.strip() if field == "title" else value)
        if tournament.is_published:
            tournament.full_clean(exclude=["organizer", "game"], validate_constraints=False)
        else:
            _validate_draft(tournament)
        tournament.save()
        if stage_format is not None:
            stage = tournament.stages.select_for_update().get(order=1)
            stage.format = StageFormat(stage_format)
            stage.full_clean(exclude=["tournament"])
            stage.save(update_fields=["format"])
    return tournament


def tournament_publish(*, by: User, tournament: Tournament) -> Tournament:
    """Make a draft public; registration opens on schedule (or now, if already due)."""
    with transaction.atomic():
        tournament = _lock(tournament.pk)
        _ensure_can_manage(by, tournament)
        if tournament.is_published or tournament.status != S.DRAFT:
            raise AlreadyPublishedError
        _validate_draft(tournament)
        tournament.published_at = timezone.now()
        tournament.save(update_fields=["published_at", "updated_at"])
        if tournament.registration_opens_at <= tournament.published_at:
            _transition(tournament, S.REGISTRATION_OPEN)
    return tournament


def tournament_cancel(*, by: User, tournament: Tournament) -> Tournament:
    with transaction.atomic():
        tournament = _lock(tournament.pk)
        _ensure_can_manage(by, tournament)
        _transition(tournament, S.CANCELLED)
    # TODO(Sprint 7): notify participants; TODO(Sprint 8): settle the prize pool;
    # TODO(Sprint 9): AuditLog entry when a moderator/admin cancels.
    return tournament


def tournament_set_status(*, tournament: Tournament, status: str) -> Tournament:
    """Move to ``status`` if the lifecycle allows it (used by schedule tasks and later flows)."""
    with transaction.atomic():
        tournament = _lock(tournament.pk)
        _transition(tournament, status)
    return tournament


def _lock(tournament_id: int) -> Tournament:
    return Tournament.objects.select_for_update().select_related("game").get(pk=tournament_id)


def _transition(tournament: Tournament, status: str) -> None:
    """Caller holds the row lock."""
    if status not in ALLOWED_TRANSITIONS[tournament.status]:
        raise InvalidStatusTransitionError
    if status == S.REGISTRATION_OPEN and not tournament.is_published:
        raise InvalidStatusTransitionError
    tournament.status = status
    tournament.save(update_fields=["status", "updated_at"])


def sync_registration_statuses(now: datetime | None = None) -> int:
    """Open and close registration of published tournaments on schedule; idempotent.

    Returns the number of status changes.
    """
    now = now or timezone.now()
    changed = 0
    due_to_open = Tournament.objects.filter(
        status=S.DRAFT, published_at__isnull=False, registration_opens_at__lte=now
    )
    for pk in due_to_open.values_list("pk", flat=True):
        changed += _advance_if(pk, S.DRAFT, S.REGISTRATION_OPEN)
    # Runs after opening, so a tournament published late moves through both steps at once.
    due_to_close = Tournament.objects.filter(
        status=S.REGISTRATION_OPEN, registration_closes_at__lte=now
    )
    for pk in due_to_close.values_list("pk", flat=True):
        changed += _advance_if(pk, S.REGISTRATION_OPEN, S.REGISTRATION_CLOSED)
    return changed


def _advance_if(tournament_id: int, expected: str, status: str) -> int:
    with transaction.atomic():
        tournament = (
            Tournament.objects.select_for_update(skip_locked=True)
            .filter(pk=tournament_id, status=expected)
            .first()
        )
        if tournament is None:
            # Changed or being changed by someone else meanwhile.
            return 0
        _transition(tournament, status)
    return 1
