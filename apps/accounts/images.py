from io import BytesIO
from uuid import uuid4

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, UnidentifiedImageError

from apps.accounts.exceptions import AvatarTooLargeError, InvalidAvatarError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def reencode_avatar(upload: UploadedFile) -> ContentFile[bytes]:
    """Validate an uploaded avatar and re-encode it as a square-bounded WebP.

    Re-encoding drops metadata and anything appended to the original file.
    """
    if upload.size is None or upload.size > settings.AVATAR_MAX_BYTES:
        raise AvatarTooLargeError
    try:
        with Image.open(upload) as image:
            # Checked before decoding pixels to reject decompression bombs early.
            if image.format not in ALLOWED_FORMATS:
                raise InvalidAvatarError
            width, height = image.size
            if width * height > settings.AVATAR_MAX_PIXELS:
                raise AvatarTooLargeError
            image.load()
            converted = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise InvalidAvatarError from error

    converted.thumbnail((settings.AVATAR_SIZE, settings.AVATAR_SIZE))
    buffer = BytesIO()
    converted.save(buffer, format="WEBP", quality=85)
    return ContentFile(buffer.getvalue(), name=f"{uuid4().hex}.webp")
