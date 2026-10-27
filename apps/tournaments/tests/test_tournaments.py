from datetime import datetime, timedelta
from typing import Any

import pytest
from allauth.account.models import EmailAddress
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.games.models import GameSlug, SeriesFormat
from apps.games.regions import Region
from apps.games.tests.factories import seeded_game
from apps.tournaments import services
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
from apps.tournaments.models import StageFormat, Tournament, TournamentStatus
from apps.tournaments.tasks import sync_registration_statuses
from apps.tournaments.tests.factories import TournamentFactory

pytestmark = pytest.mark.django_db


def verified(user: User) -> User:
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    return user


@pytest.fixture
def organizer() -> User:
    return verified(UserFactory.create())


def at(days: float) -> datetime:
    return timezone.now() + timedelta(days=days)


def schedule(**days: float) -> dict[str, datetime]:
    """Tournament dates as day offsets from one moment, so equal offsets are equal times."""
    now = timezone.now()
    offsets = {
        "registration_opens_at": 1.0,
        "registration_closes_at": 5.0,
        "checkin_opens_at": 6.0,
        "starts_at": 7.0,
    } | days
    return {field: now + timedelta(days=offset) for field, offset in offsets.items()}


def create(organizer: User, **overrides: Any) -> Tournament:
    data: dict[str, Any] = {
        "game": seeded_game(GameSlug.CS2),
        "title": "Autumn Cup",
        "rules": "Be nice.",
        "region": Region.EU,
        "max_participants": 16,
        "series_format": SeriesFormat.BO3,
        "stage_format": StageFormat.DOUBLE_ELIM,
        **schedule(),
    }
    return services.tournament_create(organizer=organizer, **(data | overrides))


def published(**kwargs: Any) -> Tournament:
    return TournamentFactory.create(published_at=timezone.now(), **kwargs)


# --- creation ------------------------------------------------------------------


def test_create_draft_with_first_stage(organizer: User) -> None:
    tournament = create(organizer)

    assert tournament.status == TournamentStatus.DRAFT
    assert not tournament.is_published
    assert tournament.organizer == organizer
    assert [(s.order, s.format) for s in tournament.stages.all()] == [(1, StageFormat.DOUBLE_ELIM)]


def test_organizer_needs_verified_email() -> None:
    with pytest.raises(EmailNotVerifiedError):
        create(UserFactory.create())


def test_game_must_be_active(organizer: User) -> None:
    game = seeded_game(GameSlug.DOTA2)
    game.is_active = False
    game.save()

    with pytest.raises(GameNotAvailableError):
        create(organizer, game=game)


@pytest.mark.parametrize(
    ("slug", "region"),
    [(GameSlug.CS2, Region.WR_RU), (GameSlug.WILDRIFT, Region.EU), (GameSlug.HEARTHSTONE, "")],
)
def test_region_must_belong_to_game(organizer: User, slug: GameSlug, region: str) -> None:
    with pytest.raises(InvalidRegionError):
        create(organizer, game=seeded_game(slug), region=region)


def test_wildrift_server_region(organizer: User) -> None:
    tournament = create(organizer, game=seeded_game(GameSlug.WILDRIFT), region=Region.WR_EUW)

    assert tournament.region == Region.WR_EUW


def test_series_must_be_allowed_by_game(organizer: User) -> None:
    game = seeded_game(GameSlug.CS2)
    game.allowed_series = [SeriesFormat.BO1]
    game.save()

    with pytest.raises(InvalidSeriesFormatError):
        create(organizer, series_format=SeriesFormat.BO5)


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"registration_opens_at": 5}, RegistrationMustOpenBeforeCloseError),
        ({"checkin_opens_at": 4}, CheckinBeforeRegistrationClosesError),
        ({"checkin_opens_at": 7}, CheckinMustOpenBeforeStartError),
        (
            {"registration_opens_at": -3, "registration_closes_at": -1},
            RegistrationClosesInPastError,
        ),
    ],
)
def test_schedule_order(
    organizer: User, overrides: dict[str, float], error: type[Exception]
) -> None:
    with pytest.raises(error):
        create(organizer, **schedule(**overrides))


def test_check_in_may_open_when_registration_closes(organizer: User) -> None:
    tournament = create(organizer, **schedule(checkin_opens_at=5))

    assert tournament.checkin_opens_at == tournament.registration_closes_at


@pytest.mark.parametrize("value", [1, 257])
def test_participant_limit(organizer: User, value: int) -> None:
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        create(organizer, max_participants=value)


def test_database_enforces_schedule_order() -> None:
    with pytest.raises(IntegrityError):
        TournamentFactory.create(checkin_opens_at=at(8))


def test_database_requires_publication_after_draft() -> None:
    with pytest.raises(IntegrityError):
        TournamentFactory.create(status=TournamentStatus.REGISTRATION_OPEN)


# --- editing -------------------------------------------------------------------


def test_organizer_edits_draft(organizer: User) -> None:
    tournament = create(organizer)

    services.tournament_update(
        by=organizer,
        tournament=tournament,
        data={"title": "Winter Cup", "max_participants": 32, "stage_format": StageFormat.SWISS},
    )

    tournament.refresh_from_db()
    assert (tournament.title, tournament.max_participants) == ("Winter Cup", 32)
    assert tournament.stages.get().format == StageFormat.SWISS


def test_edit_revalidates(organizer: User) -> None:
    tournament = create(organizer)

    with pytest.raises(CheckinMustOpenBeforeStartError):
        services.tournament_update(
            by=organizer, tournament=tournament, data={"starts_at": tournament.checkin_opens_at}
        )


def test_only_organizer_or_staff_edits(organizer: User) -> None:
    tournament = create(organizer)

    with pytest.raises(NotTournamentManagerError):
        services.tournament_update(
            by=UserFactory.create(), tournament=tournament, data={"title": "Hijacked"}
        )
    services.tournament_update(
        by=UserFactory.create(is_staff=True), tournament=tournament, data={"title": "Fixed"}
    )


def test_published_tournament_keeps_its_settings() -> None:
    tournament = published()

    services.tournament_update(
        by=tournament.organizer, tournament=tournament, data={"title": "New", "rules": "Updated"}
    )
    with pytest.raises(TournamentLockedError):
        services.tournament_update(
            by=tournament.organizer, tournament=tournament, data={"max_participants": 8}
        )


def test_finished_tournament_is_read_only() -> None:
    tournament = published(status=TournamentStatus.COMPLETED)

    with pytest.raises(TournamentLockedError):
        services.tournament_update(
            by=tournament.organizer, tournament=tournament, data={"title": "Late"}
        )


# --- publishing and status -----------------------------------------------------


def test_publish_before_registration_opens() -> None:
    tournament = TournamentFactory.create()

    services.tournament_publish(by=tournament.organizer, tournament=tournament)

    tournament.refresh_from_db()
    assert tournament.is_published
    assert tournament.status == TournamentStatus.DRAFT


def test_publish_after_registration_opened_opens_it_now() -> None:
    tournament = TournamentFactory.create(registration_opens_at=at(-1))

    services.tournament_publish(by=tournament.organizer, tournament=tournament)

    tournament.refresh_from_db()
    assert tournament.status == TournamentStatus.REGISTRATION_OPEN


def test_publish_twice() -> None:
    tournament = published()

    with pytest.raises(AlreadyPublishedError):
        services.tournament_publish(by=tournament.organizer, tournament=tournament)


def test_publish_rejects_stale_schedule() -> None:
    tournament = TournamentFactory.create(
        registration_opens_at=at(-3), registration_closes_at=at(-1)
    )

    with pytest.raises(RegistrationClosesInPastError):
        services.tournament_publish(by=tournament.organizer, tournament=tournament)


def test_publish_requires_manager() -> None:
    tournament = TournamentFactory.create()

    with pytest.raises(NotTournamentManagerError):
        services.tournament_publish(by=UserFactory.create(), tournament=tournament)


@pytest.mark.parametrize(
    "status",
    [
        TournamentStatus.DRAFT,
        TournamentStatus.REGISTRATION_OPEN,
        TournamentStatus.CHECKIN,
        TournamentStatus.IN_PROGRESS,
    ],
)
def test_cancel_before_completion(status: TournamentStatus) -> None:
    tournament = published(status=status)

    services.tournament_cancel(by=tournament.organizer, tournament=tournament)

    tournament.refresh_from_db()
    assert tournament.status == TournamentStatus.CANCELLED


@pytest.mark.parametrize("status", [TournamentStatus.COMPLETED, TournamentStatus.CANCELLED])
def test_cannot_cancel_finished(status: TournamentStatus) -> None:
    tournament = published(status=status)

    with pytest.raises(InvalidStatusTransitionError):
        services.tournament_cancel(by=tournament.organizer, tournament=tournament)


@pytest.mark.parametrize(
    ("current", "target", "allowed"),
    [
        (TournamentStatus.DRAFT, TournamentStatus.REGISTRATION_OPEN, True),
        (TournamentStatus.REGISTRATION_OPEN, TournamentStatus.REGISTRATION_CLOSED, True),
        (TournamentStatus.REGISTRATION_CLOSED, TournamentStatus.CHECKIN, True),
        (TournamentStatus.CHECKIN, TournamentStatus.IN_PROGRESS, True),
        (TournamentStatus.IN_PROGRESS, TournamentStatus.COMPLETED, True),
        (TournamentStatus.DRAFT, TournamentStatus.IN_PROGRESS, False),
        (TournamentStatus.REGISTRATION_OPEN, TournamentStatus.DRAFT, False),
        (TournamentStatus.COMPLETED, TournamentStatus.IN_PROGRESS, False),
        (TournamentStatus.CANCELLED, TournamentStatus.REGISTRATION_OPEN, False),
    ],
)
def test_status_transitions(
    current: TournamentStatus, target: TournamentStatus, allowed: bool
) -> None:
    tournament = published(status=current)

    if allowed:
        services.tournament_set_status(tournament=tournament, status=target)
        tournament.refresh_from_db()
        assert tournament.status == target
    else:
        with pytest.raises(InvalidStatusTransitionError):
            services.tournament_set_status(tournament=tournament, status=target)


def test_unpublished_draft_cannot_open_registration() -> None:
    tournament = TournamentFactory.create()

    with pytest.raises(InvalidStatusTransitionError):
        services.tournament_set_status(
            tournament=tournament, status=TournamentStatus.REGISTRATION_OPEN
        )


# --- schedule task -------------------------------------------------------------


def test_schedule_opens_and_closes_registration() -> None:
    due = published(registration_opens_at=at(-1))
    hidden = TournamentFactory.create(registration_opens_at=at(-1))
    future = published()
    closing = published(
        status=TournamentStatus.REGISTRATION_OPEN,
        registration_opens_at=at(-3),
        registration_closes_at=at(-0.5),
    )

    sync_registration_statuses()
    sync_registration_statuses()  # idempotent

    statuses = dict(Tournament.objects.values_list("pk", "status"))
    assert statuses == {
        due.pk: TournamentStatus.REGISTRATION_OPEN,
        hidden.pk: TournamentStatus.DRAFT,
        future.pk: TournamentStatus.DRAFT,
        closing.pk: TournamentStatus.REGISTRATION_CLOSED,
    }


def test_late_published_draft_skips_straight_to_closed() -> None:
    tournament = published(
        registration_opens_at=at(-3), registration_closes_at=at(-1), checkin_opens_at=at(1)
    )

    sync_registration_statuses()

    tournament.refresh_from_db()
    assert tournament.status == TournamentStatus.REGISTRATION_CLOSED


# --- API -----------------------------------------------------------------------


def api_payload(**overrides: Any) -> dict[str, Any]:
    data = {
        "game": "cs2",
        "title": "API Cup",
        "rules": "",
        "region": "eu",
        "max_participants": 8,
        "series_format": 3,
        "stage_format": "single_elim",
        **{key: value.isoformat() for key, value in schedule().items()},
    }
    return data | overrides


def test_api_create(api_client: APIClient, organizer: User) -> None:
    api_client.force_authenticate(organizer)

    response = api_client.post("/api/v1/tournaments/", api_payload(), format="json")

    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["status"] == "draft"
    assert data["published_at"] is None
    assert data["stages"] == [{"order": 1, "format": "single_elim", "settings": {}}]
    assert data["starts_at"].endswith("Z")


def test_api_create_reports_field_errors(api_client: APIClient, organizer: User) -> None:
    api_client.force_authenticate(organizer)

    response = api_client.post("/api/v1/tournaments/", api_payload(region="wr_ru"), format="json")

    assert response.status_code == 400
    assert "region" in response.json()


def test_api_create_requires_verified_email(api_client: APIClient) -> None:
    api_client.force_authenticate(UserFactory.create())

    response = api_client.post("/api/v1/tournaments/", api_payload(), format="json")

    assert response.status_code == 403


def test_api_list_shows_only_published(api_client: APIClient) -> None:
    published(title="Public")
    TournamentFactory.create(title="Secret")

    response = api_client.get("/api/v1/tournaments/")

    assert [t["title"] for t in response.json()["results"]] == ["Public"]


def test_api_draft_visible_to_organizer_only(api_client: APIClient) -> None:
    tournament = TournamentFactory.create()
    url = f"/api/v1/tournaments/{tournament.pk}/"

    assert api_client.get(url).status_code == 404
    api_client.force_authenticate(tournament.organizer)
    assert api_client.get(url).status_code == 200


def test_api_my_tournaments_include_drafts(api_client: APIClient) -> None:
    tournament = TournamentFactory.create()
    TournamentFactory.create()
    api_client.force_authenticate(tournament.organizer)

    response = api_client.get("/api/v1/me/tournaments/")

    assert [t["id"] for t in response.json()] == [tournament.pk]


def test_api_update_publish_cancel(api_client: APIClient) -> None:
    tournament = TournamentFactory.create()
    api_client.force_authenticate(tournament.organizer)
    url = f"/api/v1/tournaments/{tournament.pk}/"

    response = api_client.patch(url, {"title": "Renamed"}, format="json")
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed"

    response = api_client.post(f"{url}publish/")
    assert response.status_code == 200
    assert response.json()["published_at"] is not None

    response = api_client.post(f"{url}cancel/")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_api_update_by_stranger_is_forbidden(api_client: APIClient) -> None:
    tournament = published()
    api_client.force_authenticate(UserFactory.create())

    response = api_client.patch(
        f"/api/v1/tournaments/{tournament.pk}/", {"title": "X"}, format="json"
    )

    assert response.status_code == 403
