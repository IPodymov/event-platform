from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.games.models import Game
from apps.teams.exceptions import (
    AlreadyInTeamError,
    InvalidLogoError,
    LogoTooLargeError,
    NotATeamGameError,
    TeamNameTakenError,
    TeamTagTakenError,
)
from apps.teams.models import Team, TeamMembership, TeamRole
from apps.teams.selectors import has_active_team, is_team_name_taken, is_team_tag_taken
from config.images import ImageTooLargeError, InvalidImageError, reencode_image


def _reencode_logo(upload: UploadedFile) -> ContentFile[bytes]:
    try:
        return reencode_image(upload, size=settings.TEAM_LOGO_SIZE)
    except ImageTooLargeError as error:
        raise LogoTooLargeError from error
    except InvalidImageError as error:
        raise InvalidLogoError from error


def team_create(
    *, user: User, game: Game, name: str, tag: str, logo: UploadedFile | None = None
) -> Team:
    """Create a team with ``user`` as its captain."""
    name, tag = name.strip(), tag.strip()
    if not game.is_team or not game.is_active:
        raise NotATeamGameError
    if has_active_team(user, game):
        raise AlreadyInTeamError
    if is_team_name_taken(game, name):
        raise TeamNameTakenError
    if is_team_tag_taken(game, tag):
        raise TeamTagTakenError

    team = Team(game=game, name=name, tag=tag, captain=user)
    team.full_clean(exclude=["logo"])
    logo_content = _reencode_logo(logo) if logo is not None else None
    try:
        with transaction.atomic():
            team.save()
            TeamMembership.objects.create(team=team, user=user, game=game, role=TeamRole.CAPTAIN)
            # Written last: constraint violations above happen before any file exists.
            if logo_content is not None:
                team.logo.save(logo_content.name or "logo.webp", logo_content)
    except IntegrityError as error:
        # Lost a race: someone took the name/tag or the user joined another team meanwhile.
        if has_active_team(user, game):
            raise AlreadyInTeamError from error
        if is_team_tag_taken(game, tag):
            raise TeamTagTakenError from error
        raise TeamNameTakenError from error
    return team
