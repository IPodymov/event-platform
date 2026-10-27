from celery import shared_task

from apps.tournaments import services


@shared_task
def sync_registration_statuses() -> int:
    """Open and close tournament registration on schedule (Celery Beat, every minute)."""
    return services.sync_registration_statuses()
