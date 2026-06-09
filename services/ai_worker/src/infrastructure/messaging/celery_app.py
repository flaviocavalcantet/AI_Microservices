"""Celery application setup for ai-worker."""

from celery import Celery

from ...config import Config, get_config
from ...logger import setup_logging


def create_celery_app(config: Config = None) -> Celery:
    """Create a Celery app configured for RabbitMQ-backed worker execution."""

    if config is None:
        config = get_config()

    setup_logging(config.LOG_LEVEL, config.LOG_FORMAT)

    app = Celery(
        "ai_worker",
        broker=config.CELERY_BROKER_URL,
        backend=config.CELERY_RESULT_BACKEND,
        include=["services.ai_worker.src.infrastructure.tasks.health"],
    )

    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_default_queue=config.CELERY_TASK_DEFAULT_QUEUE,
        worker_concurrency=config.CELERY_WORKER_CONCURRENCY,
        task_time_limit=config.CELERY_TASK_TIME_LIMIT_SECONDS,
        task_track_started=True,
        broker_connection_retry_on_startup=True,
        task_routes={
            "notification_service.events.consume": {"queue": "notifications.default"},
        },
    )
    return app


celery = create_celery_app()
