"""Celery application setup for notification-service."""

from celery import Celery

from ...config import Config, get_config
from ...logger import setup_logging


def create_celery_app(config: Config = None) -> Celery:
    """Create RabbitMQ-ready Celery app for event consumption."""

    if config is None:
        config = get_config()

    setup_logging(config.LOG_LEVEL, config.LOG_FORMAT)

    app = Celery(
        "notification_service",
        broker=config.CELERY_BROKER_URL,
        backend=config.CELERY_RESULT_BACKEND,
        include=["services.notification_service.src.infrastructure.tasks.events"],
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_default_queue=config.CELERY_TASK_DEFAULT_QUEUE,
        worker_concurrency=config.CELERY_WORKER_CONCURRENCY,
        task_track_started=True,
        broker_connection_retry_on_startup=True,
    )
    return app


celery = create_celery_app()
