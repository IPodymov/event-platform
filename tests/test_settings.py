from django.conf import settings


def test_timestamps_are_stored_in_utc() -> None:
    assert settings.USE_TZ is True
    assert settings.TIME_ZONE == "UTC"


def test_default_language_is_russian() -> None:
    assert settings.LANGUAGE_CODE == "ru"


def test_celery_runs_tasks_eagerly_in_tests() -> None:
    # Defined only in test settings, which mypy does not load.
    assert getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False) is True
