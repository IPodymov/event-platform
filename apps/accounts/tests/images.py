from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image


def image_upload(
    *, size: tuple[int, int] = (800, 600), fmt: str = "PNG", name: str = "avatar.png"
) -> SimpleUploadedFile:
    buffer = BytesIO()
    Image.new("RGB", size, color=(200, 30, 30)).save(buffer, format=fmt)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{fmt.lower()}")
