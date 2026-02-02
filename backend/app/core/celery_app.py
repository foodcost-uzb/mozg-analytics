from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "mozg_analytics",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.services.sync.tasks",
        "app.telegram.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",  # Moscow timezone for reports
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3000,  # 50 minutes
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
)

# Periodic tasks schedule
celery_app.conf.beat_schedule = {
    # Full sync every night at 3:00 AM
    "full-sync-daily": {
        "task": "app.services.sync.tasks.full_sync_all_venues",
        "schedule": crontab(hour=3, minute=0),
    },
    # Incremental sync every 15 minutes
    "incremental-sync": {
        "task": "app.services.sync.tasks.incremental_sync_all_venues",
        "schedule": crontab(minute="*/15"),
    },
    # Aggregate daily sales at midnight
    "aggregate-daily-sales": {
        "task": "app.services.sync.tasks.aggregate_daily_sales",
        "schedule": crontab(hour=0, minute=5),
    },
    # Telegram: Morning reports at 9:00 AM Moscow
    "telegram-morning-reports": {
        "task": "telegram.send_morning_reports",
        "schedule": crontab(hour=9, minute=0),
    },
    # Telegram: Evening reports at 10:00 PM Moscow
    "telegram-evening-reports": {
        "task": "telegram.send_evening_reports",
        "schedule": crontab(hour=22, minute=0),
    },
    # Telegram: Check anomalies every 2 hours
    "telegram-anomaly-check": {
        "task": "telegram.check_and_send_anomalies",
        "schedule": crontab(minute=0, hour="*/2"),
    },
}
