"""Validation and re-encoding of user-uploaded images (avatars, team logos)."""

from io import BytesIO
from uuid import uuid4

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class InvalidImageError(Exception):
    """The upload is not a JPEG, PNG or WebP image."""


class ImageTooLargeError(InvalidImageError):
    """The upload exceeds the byte or pixel limit."""


def reencode_image(upload: UploadedFile, *, size: int) -> ContentFile[bytes]:
    """Validate an uploaded image and re-encode it as WebP within ``size`` x ``size``.

    Re-encoding drops metadata and anything appended to the original file.
    """
    if upload.size is None or upload.size > settings.UPLOAD_IMAGE_MAX_BYTES:
        raise ImageTooLargeError
    try:
        with Image.open(upload) as image:
            # Checked before decoding pixels to reject decompression bombs early.
            if image.format not in ALLOWED_FORMATS:
                raise InvalidImageError
            width, height = image.size
            if width * height > settings.UPLOAD_IMAGE_MAX_PIXELS:
                raise ImageTooLargeError
            image.load()
            converted = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise InvalidImageError from error

    converted.thumbnail((size, size))
    buffer = BytesIO()
    converted.save(buffer, format="WEBP", quality=85)
    return ContentFile(buffer.getvalue(), name=f"{uuid4().hex}.webp")
