import os
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from django.core.cache import cache
from hypothesis import settings as hypothesis_settings
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

if TYPE_CHECKING:
    from apps.accounts.models import User

hypothesis_settings.register_profile("ci", max_examples=200, deadline=None)
hypothesis_settings.register_profile("dev", max_examples=50, deadline=None)
hypothesis_settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))


@pytest.fixture(autouse=True)
def _isolated_media_root(settings: Settings, tmp_path: Path) -> None:
    """Keep uploaded files out of the project directory."""
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    """Rate limits live in the cache; keep them from leaking between tests."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db: None) -> "User":
    # Imported lazily: models must not load before pytest-django sets up Django.
    from apps.accounts.tests.factories import UserFactory

    return UserFactory.create()
