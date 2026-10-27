import secrets
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import Profile, User
from apps.games.models import Game
from apps.teams.exceptions import (
    AlreadyInTeamError,
    AlreadyInvitedError,
    AlreadyMemberError,
    CannotRemoveCaptainError,
    CaptainMustTransferError,
    InvalidLogoError,
    InvalidRoleError,
    InviteNotActiveError,
    LogoTooLargeError,
    NotATeamGameError,
    NotInviteeError,
    NotTeamCaptainError,
    NotTeamMemberError,
    PlayerNotFoundError,
    RosterFullError,
    TeamDisbandedError,
    TeamNameTakenError,
    TeamTagTakenError,
)
from apps.teams.models import InviteStatus, Team, TeamInvite, TeamMembership, TeamRole
from apps.teams.selectors import (
    active_memberships,
    count_active_roles,
    has_active_team,
    is_team_member,
    is_team_name_taken,
    is_team_tag_taken,
    pending_invites,
)
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


def _role_capacity(game: Game, role: str) -> int:
    # The captain plays in the main roster.
    return game.roster_size if role in (TeamRole.PLAYER, TeamRole.CAPTAIN) else game.max_substitutes


def _has_free_slot(team: Team, role: str) -> bool:
    counts = count_active_roles(team)
    taken = counts.get(TeamRole.SUBSTITUTE, 0)
    if role != TeamRole.SUBSTITUTE:
        taken = counts.get(TeamRole.PLAYER, 0) + counts.get(TeamRole.CAPTAIN, 0)
    return taken < _role_capacity(team.game, role)


def _ensure_captain(team: Team, user: User) -> None:
    if team.captain_id != user.pk:
        raise NotTeamCaptainError


def _ensure_not_disbanded(team: Team) -> None:
    if team.is_disbanded:
        raise TeamDisbandedError


def _lock_team(team_id: int) -> Team:
    """Lock the team row; roster changes of one team are serialized through it."""
    return Team.objects.select_for_update().select_related("game").get(pk=team_id)


def _lock_membership(team: Team, membership_id: int) -> TeamMembership:
    membership = (
        TeamMembership.objects.select_for_update()
        .filter(pk=membership_id, team=team, left_at__isnull=True)
        .first()
    )
    if membership is None:
        raise NotTeamMemberError
    return membership


def _ensure_pending(invite: TeamInvite) -> None:
    if invite.status != InviteStatus.PENDING or invite.expires_at <= timezone.now():
        raise InviteNotActiveError


def invite_create(
    *, by: User, team: Team, role: str = TeamRole.PLAYER, nickname: str | None = None
) -> TeamInvite:
    """Invite a player by nickname, or create a shareable link when ``nickname`` is empty."""
    _ensure_captain(team, by)
    _ensure_not_disbanded(team)
    invitee: User | None = None
    if nickname:
        profile = Profile.objects.select_related("user").filter(nickname__iexact=nickname).first()
        if profile is None or not profile.user.is_active:
            raise PlayerNotFoundError
        invitee = profile.user
        if is_team_member(team, invitee):
            raise AlreadyMemberError
        if pending_invites().filter(team=team, invitee=invitee).exists():
            raise AlreadyInvitedError
    if not _has_free_slot(team, role):
        raise RosterFullError

    invite = TeamInvite(
        team=team,
        invitee=invitee,
        role=role,
        created_by=by,
        token=secrets.token_urlsafe(32),
        expires_at=timezone.now() + timedelta(days=settings.TEAM_INVITE_TTL_DAYS),
    )
    with transaction.atomic():
        # An expired pending invite would block the partial unique index; close it first.
        if invitee is not None:
            TeamInvite.objects.filter(
                team=team, invitee=invitee, status=InviteStatus.PENDING
            ).update(status=InviteStatus.REVOKED, responded_at=timezone.now())
        invite.save()
    # TODO(Sprint 7): notify the invitee (invite_received) after commit.
    return invite


def invite_accept(*, user: User, invite: TeamInvite) -> TeamMembership:
    """Join the team; personal invites are closed, link invites stay usable."""
    if invite.invitee_id is not None and invite.invitee_id != user.pk:
        raise NotInviteeError
    with transaction.atomic():
        # Serializes acceptances per team so capacity checks cannot race.
        team = _lock_team(invite.team_id)
        invite = TeamInvite.objects.select_for_update().get(pk=invite.pk)
        _ensure_pending(invite)
        _ensure_not_disbanded(team)
        if is_team_member(team, user):
            raise AlreadyMemberError
        if has_active_team(user, team.game):
            raise AlreadyInTeamError
        if not _has_free_slot(team, invite.role):
            raise RosterFullError
        membership = TeamMembership.objects.create(
            team=team, user=user, game=team.game, role=invite.role
        )
        if not invite.is_link:
            invite.status, invite.responded_at = InviteStatus.ACCEPTED, timezone.now()
            invite.save(update_fields=["status", "responded_at"])
    return membership


def invite_decline(*, user: User, invite: TeamInvite) -> None:
    if invite.invitee_id != user.pk:
        raise NotInviteeError
    _ensure_pending(invite)
    invite.status, invite.responded_at = InviteStatus.DECLINED, timezone.now()
    invite.save(update_fields=["status", "responded_at"])


def invite_revoke(*, by: User, invite: TeamInvite) -> None:
    _ensure_captain(invite.team, by)
    if invite.status != InviteStatus.PENDING:
        raise InviteNotActiveError
    invite.status, invite.responded_at = InviteStatus.REVOKED, timezone.now()
    invite.save(update_fields=["status", "responded_at"])


# --- roster management --------------------------------------------------------
# TODO(Sprint 3): decide whether roster changes are blocked while the team is
# registered in an unfinished tournament (the registration keeps roster_snapshot).


def member_change_role(*, by: User, team: Team, membership_id: int, role: str) -> TeamMembership:
    """Move a member between player and substitute."""
    if role not in (TeamRole.PLAYER, TeamRole.SUBSTITUTE):
        raise InvalidRoleError
    with transaction.atomic():
        team = _lock_team(team.pk)
        _ensure_captain(team, by)
        _ensure_not_disbanded(team)
        membership = _lock_membership(team, membership_id)
        if membership.role == TeamRole.CAPTAIN:
            raise CannotRemoveCaptainError
        if membership.role != role and not _has_free_slot(team, role):
            raise RosterFullError
        membership.role = role
        membership.save(update_fields=["role"])
    return membership


def captain_transfer(*, by: User, team: Team, membership_id: int) -> Team:
    """Make another member captain; the old captain takes over their previous role."""
    with transaction.atomic():
        team = _lock_team(team.pk)
        _ensure_captain(team, by)
        _ensure_not_disbanded(team)
        new_captain = _lock_membership(team, membership_id)
        if new_captain.role == TeamRole.CAPTAIN:
            return team
        old_captain = TeamMembership.objects.select_for_update().get(
            team=team, role=TeamRole.CAPTAIN, left_at__isnull=True
        )
        # Swapping roles keeps the main roster and substitutes counts unchanged.
        # The old captain is demoted first: one active captain per team is a DB constraint.
        old_captain.role = new_captain.role
        old_captain.save(update_fields=["role"])
        new_captain.role = TeamRole.CAPTAIN
        new_captain.save(update_fields=["role"])
        team.captain_id = new_captain.user_id
        team.save(update_fields=["captain", "updated_at"])
    return team


def member_remove(*, by: User, team: Team, membership_id: int) -> None:
    with transaction.atomic():
        team = _lock_team(team.pk)
        _ensure_captain(team, by)
        membership = _lock_membership(team, membership_id)
        if membership.role == TeamRole.CAPTAIN:
            raise CannotRemoveCaptainError
        membership.left_at = timezone.now()
        membership.save(update_fields=["left_at"])


def member_leave(*, user: User, team: Team) -> None:
    """Leave the team. A captain may only leave as the last member, which disbands the team."""
    with transaction.atomic():
        team = _lock_team(team.pk)
        membership = (
            TeamMembership.objects.select_for_update()
            .filter(team=team, user=user, left_at__isnull=True)
            .first()
        )
        if membership is None:
            raise NotTeamMemberError
        now = timezone.now()
        if membership.role == TeamRole.CAPTAIN:
            if active_memberships().filter(team=team).exclude(pk=membership.pk).exists():
                raise CaptainMustTransferError
            team.disbanded_at = now
            team.save(update_fields=["disbanded_at", "updated_at"])
            TeamInvite.objects.filter(team=team, status=InviteStatus.PENDING).update(
                status=InviteStatus.REVOKED, responded_at=now
            )
        membership.left_at = now
        membership.save(update_fields=["left_at"])
