from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "job_board_api",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)

celery_app.conf.beat_schedule = {
    "cleanup-expired-jobs-daily": {
        "task": "app.tasks.cleanup_expired_jobs_task",
        "schedule": crontab(hour=3, minute=0),  # every day at 03:00 UTC
    },
    "worker-heartbeat": {
        "task": "app.tasks.heartbeat_task",
        "schedule": crontab(minute="*/5"),
    },
}