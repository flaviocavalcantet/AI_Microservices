"""Event publisher - sends job lifecycle events to notification-service via RabbitMQ."""

import logging
from typing import Any, Dict
from uuid import uuid4

logger = logging.getLogger(__name__)

# Queue notification-service listens on
_NOTIFICATION_QUEUE = "notifications.default"


class JobEventPublisher:
    """Publishes job.completed and job.failed events to the notification-service queue."""

    def publish_job_completed(self, job_id: str, result: Dict[str, Any]) -> None:
        self._publish("job.completed", job_id, {"result": result})

    def publish_job_failed(self, job_id: str, error: str) -> None:
        self._publish("job.failed", job_id, {"error": error})

    def _publish(self, event_type: str, job_id: str, extra: Dict[str, Any]) -> None:
        from celery import current_app

        event_data = {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "source": "ai_worker",
            "payload": {"job_id": job_id, **extra},
        }

        try:
            current_app.send_task(
                "notification_service.events.consume",
                kwargs={"event_data": event_data},
                queue=_NOTIFICATION_QUEUE,
            )
            logger.info("Published %s for job %s", event_type, job_id)
        except Exception as exc:
            # Publishing is best-effort — never let it break job state transitions
            logger.warning("Failed to publish %s for job %s: %s", event_type, job_id, exc)
