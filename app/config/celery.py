"""Celery app and beat schedule."""

from celery import Celery
from celery.schedules import crontab

from app.config.settings import settings

celery_app = Celery(
    "pivota",
    broker=f"{settings.redis_url}/{settings.redis_db_celery}",
    backend=f"{settings.redis_url}/{settings.redis_db_celery}",
    include=[
        "app.workers.ingest_tasks",
        "app.workers.report_tasks",
        "app.workers.analytics_tasks",
        "app.workers.notification_tasks",
        "app.workers.compliance_tasks",
        "app.workers.dlq_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
)

celery_app.conf.beat_schedule = {
    "poll-momo-transactions": {
        "task": "app.workers.ingest_tasks.poll_momo_transactions",
        "schedule": crontab(minute="*/5"),
    },
    "trigger-monthly-reports": {
        "task": "app.workers.report_tasks.trigger_monthly_reports",
        "schedule": crontab(day_of_month="1", hour="8", minute="0"),
    },
    "precompute-weekly-summaries": {
        "task": "app.workers.analytics_tasks.precompute_weekly_summaries",
        "schedule": crontab(day_of_week="0", hour="0", minute="0"),
    },
    "check-dlq-depth": {
        "task": "app.workers.dlq_tasks.check_dlq_depth",
        "schedule": crontab(minute="0"),
    },
}
