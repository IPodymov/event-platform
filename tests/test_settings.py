from django.apps import apps
from django.conf import settings


def test_timestamps_are_stored_in_utc() -> None:
    assert settings.USE_TZ is True
    assert settings.TIME_ZONE == "UTC"


def test_default_language_is_russian() -> None:
    assert settings.LANGUAGE_CODE == "ru"


def test_celery_runs_tasks_eagerly_in_tests() -> None:
    # Defined only in test settings, which mypy does not load.
    assert getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False) is True


def test_project_apps_use_big_auto_field() -> None:
    # DEFAULT_AUTO_FIELD is AutoField for third-party apps, so ours must opt in.
    project_apps = [c for c in apps.get_app_configs() if c.name.startswith("apps.")]

    assert project_apps
    assert {c.default_auto_field for c in project_apps} == {"django.db.models.BigAutoField"}
