"""RabbitMQ job dispatcher for api-service.

Publishes a job payload to the ``ai.default`` Celery queue so that
``celery-worker-ai`` can pick it up and execute it.

This module has NO AI or heavy dependencies — it uses only Celery's
producer API (kombu under the hood) that is already a transitive dep
via the broker infrastructure.

The task name ``ai_worker.jobs.execute`` must match the ``@celery.task``
registered in ``celery-worker-ai``.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

_AI_TASK_NAME = "ai_worker.jobs.execute"
_AI_QUEUE = "ai.default"


class RabbitMQJobDispatcher:
    """Dispatches jobs to ``celery-worker-ai`` via RabbitMQ.

    Uses Celery's ``send_task`` so the api-service does not need its own
    Celery worker — it only acts as a producer.
    """

    def __init__(self, broker_url: str) -> None:
        """Create a dispatcher bound to *broker_url*.

        Args:
            broker_url: RabbitMQ AMQP URL
                        (e.g. ``amqp://user:pass@rabbitmq:5672/``).
        """
        from celery import Celery

        self._app = Celery(broker=broker_url)
        self._app.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            broker_connection_retry_on_startup=True,
        )
        logger.info("RabbitMQJobDispatcher initialised (broker: %s)", broker_url)

    def dispatch(self, job_id: str, job_payload: Dict[str, Any]) -> None:
        """Send *job_payload* to the AI worker queue.

        Args:
            job_id:      The MongoDB job ID (UUID string).
            job_payload: The full job dict the worker task receives.
                         Must include ``job_id``, ``job_type``,
                         ``input_data``, ``user_id``, ``priority``,
                         and ``timeout_seconds``.

        Raises:
            Exception: Re-raises any Celery/broker error so the caller
                       can decide whether to treat it as fatal.
        """
        try:
            self._app.send_task(
                _AI_TASK_NAME,
                kwargs={"job_payload": job_payload},
                queue=_AI_QUEUE,
            )
            logger.info(
                "Job dispatched to RabbitMQ queue '%s': %s",
                _AI_QUEUE,
                job_id,
            )
        except Exception as exc:
            logger.error(
                "Failed to dispatch job %s to queue '%s': %s",
                job_id,
                _AI_QUEUE,
                exc,
            )
            raise
