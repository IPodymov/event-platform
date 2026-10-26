import os
from pathlib import Path

import pytest
from hypothesis import settings as hypothesis_settings
from pytest_django.fixtures import Settings

hypothesis_settings.register_profile("ci", max_examples=200, deadline=None)
hypothesis_settings.register_profile("dev", max_examples=50, deadline=None)
hypothesis_settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))


@pytest.fixture(autouse=True)
def _isolated_media_root(settings: Settings, tmp_path: Path) -> None:
    """Keep uploaded files out of the project directory."""
    settings.MEDIA_ROOT = tmp_path / "media"
