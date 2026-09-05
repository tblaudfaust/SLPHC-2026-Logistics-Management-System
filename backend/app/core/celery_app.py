from celery import Celery

from app.core.config import settings

celery_app = Celery("slphc", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "check-overdue-transfers-hourly": {
            "task": "notifications.check_overdue_transfers",
            "schedule": 3600.0,
        },
    },
)

# Imported after celery_app is constructed (task modules decorate with
# @celery_app.task, so they need the instance to already exist — importing
# up top would be circular, since notification_tasks imports celery_app).
from app.services import notification_tasks  # noqa: E402,F401
