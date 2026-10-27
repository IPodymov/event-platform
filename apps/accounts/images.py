from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile

from apps.accounts.exceptions import AvatarTooLargeError, InvalidAvatarError
from config.images import ImageTooLargeError, InvalidImageError, reencode_image


def reencode_avatar(upload: UploadedFile) -> ContentFile[bytes]:
    try:
        return reencode_image(upload, size=settings.AVATAR_SIZE)
    except ImageTooLargeError as error:
        raise AvatarTooLargeError from error
    except InvalidImageError as error:
        raise InvalidAvatarError from error
