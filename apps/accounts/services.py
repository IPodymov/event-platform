from typing import Any

from django.core.files.uploadedfile import UploadedFile
from django.db import IntegrityError, transaction

from apps.accounts.exceptions import (
    NicknameTakenError,
    SocialAccountAlreadyLinkedError,
    SocialSignupNotAllowedError,
)
from apps.accounts.images import reencode_avatar
from apps.accounts.models import Profile, User
from apps.accounts.selectors import get_social_uid, is_nickname_taken

PROFILE_EDITABLE_FIELDS = frozenset({"nickname", "country", "timezone", "bio"})


def validate_social_link(*, user: User, provider: str, uid: str) -> None:
    """Allow linking unless the user already has a different account of ``provider``."""
    linked = get_social_uid(user, provider)
    if linked is not None and linked != uid:
        raise SocialAccountAlreadyLinkedError


def validate_social_login(*, is_linked: bool) -> None:
    """Third-party providers are linked identities only: they never create accounts."""
    if not is_linked:
        raise SocialSignupNotAllowedError


def profile_create(*, user: User, nickname: str) -> Profile:
    if is_nickname_taken(nickname):
        raise NicknameTakenError
    profile = Profile(user=user, nickname=nickname)
    profile.full_clean()
    try:
        # Savepoint: a lost race on the unique constraint must not break the outer transaction.
        with transaction.atomic():
            profile.save()
    except IntegrityError as error:
        raise NicknameTakenError from error
    return profile


def profile_update(
    *, profile: Profile, data: dict[str, Any], avatar: UploadedFile | None = None
) -> Profile:
    """Update editable profile fields and optionally replace the avatar."""
    unknown = set(data) - PROFILE_EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"Not editable: {sorted(unknown)}")
    nickname = data.get("nickname")
    if nickname is not None and is_nickname_taken(nickname, exclude_profile_id=profile.pk):
        raise NicknameTakenError

    for field, value in data.items():
        setattr(profile, field, value)
    old_avatar_name = profile.avatar.name if avatar is not None else ""
    if avatar is not None:
        content = reencode_avatar(avatar)
        profile.avatar.save(content.name or "avatar.webp", content, save=False)
    storage = profile.avatar.storage
    try:
        profile.full_clean()
        with transaction.atomic():
            profile.save()
            if old_avatar_name:
                transaction.on_commit(lambda: storage.delete(old_avatar_name))
    except Exception as error:
        if avatar is not None:
            storage.delete(profile.avatar.name)
        if isinstance(error, IntegrityError):
            raise NicknameTakenError from error
        raise
    return profile
