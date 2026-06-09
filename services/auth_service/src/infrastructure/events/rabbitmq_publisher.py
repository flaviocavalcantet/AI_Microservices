"""RabbitMQ event publisher for auth-service domain events."""

from __future__ import annotations

import logging
from typing import Any

from celery import Celery

from ...application.ports.interfaces import IEventPublisher

logger = logging.getLogger(__name__)

_NOTIFICATION_QUEUE = "notifications.default"


class RabbitMQEventPublisher(IEventPublisher):
    """Publishes auth domain events to notification-service via RabbitMQ."""

    def __init__(self, broker_url: str) -> None:
        self._broker_url = broker_url
        self._celery: Celery | None = None

    def _get_celery(self) -> Celery:
        if self._celery is None:
            self._celery = Celery(broker=self._broker_url)
        return self._celery

    def publish(self, event: Any) -> None:
        event_data = {
            "event_id": getattr(event, "event_id", None),
            "event_type": getattr(event, "event_type", type(event).__name__),
            "source": "auth_service",
            "payload": {
                k: v for k, v in vars(event).items()
                if k not in ("event_id",)
            },
        }

        try:
            self._get_celery().send_task(
                "notification_service.events.consume",
                kwargs={"event_data": event_data},
                queue=_NOTIFICATION_QUEUE,
            )
            logger.info("Published %s", event_data["event_type"])
        except Exception as exc:
            logger.warning("Failed to publish %s: %s", event_data["event_type"], exc)
