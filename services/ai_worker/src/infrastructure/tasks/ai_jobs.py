"""AI job execution Celery task.

This is the **only** place AI workloads are executed in the entire
platform.  The task:

1. Receives a ``job_payload`` dict published by ``api-service`` to the
   ``ai.default`` RabbitMQ queue.
2. Marks the job as ``running`` in the api-service MongoDB collection.
3. Delegates execution to ``PlaceholderWorkloadRunner`` (raises
   ``NotImplementedError`` until real models are wired in).
4. Calls ``JobManager.complete_job()`` or ``JobManager.fail_job()``.
   Both methods automatically publish a ``job.completed`` /
   ``job.failed`` event to the ``notifications.default`` queue, which
   ``celery-worker-notification`` consumes.
5. Writes the terminal status back to the api-service MongoDB record
   so ``api-service`` can return it via ``GET /api/v1/jobs/{id}/status``
   without any further HTTP fan-out.

Constraints honoured
--------------------
* No model imports here — ``PlaceholderWorkloadRunner`` is the only
  workload class used; real runners live in their own modules and are
  injected at runtime.
* ``ai-worker`` Flask service is not called \u2014 we instantiate the shared
  ``JobManager`` + ``JobEventPublisher`` directly inside the task process.
* The notification flow is unchanged: ``JobManager`` calls
  ``JobEventPublisher._publish()`` which uses ``celery.current_app``
  (the same Celery app this worker runs under) to send to
  ``notifications.default``.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict

from ..messaging.celery_app import celery
from ..jobs.job_manager import JobManager
from ..messaging.event_publisher import JobEventPublisher
from ..workloads.placeholder_runner import PlaceholderWorkloadRunner

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_api_service_jobs_collection():
    """Return a pymongo Collection for the api-service ``jobs`` collection.

    Uses the ``API_SERVICE_MONGODB_URI`` environment variable
    (set in docker-compose for the celery-worker-ai service).
    Falls back to a sensible localhost default for local dev.
    """
    from pymongo import MongoClient

    uri = os.environ.get(
        "API_SERVICE_MONGODB_URI",
        "mongodb://admin:admin123@localhost:27017/api_service?authSource=admin",
    )
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    db = client.get_database()
    return db["jobs"]


def _update_api_job_status(
    job_id: str,
    status: str,
    result: Dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """Persist a status change back to the api-service MongoDB ``jobs`` record.

    This keeps ``api-service`` in sync without requiring an HTTP call into
    the ``ai-worker`` Flask service.

    Silently logs and swallows errors — a MongoDB write failure here must
    never cause the Celery task to crash after the workload has already run,
    because the notification event has already been fired by ``JobManager``.
    """
    try:
        from datetime import datetime, timezone
        from bson import ObjectId

        jobs = _get_api_service_jobs_collection()

        update_fields: Dict[str, Any] = {
            "status": status,
            "updated_at": datetime.now(timezone.utc),
        }

        if status == "running":
            update_fields["started_at"] = datetime.now(timezone.utc)

        if status in ("completed", "failed", "cancelled"):
            update_fields["completed_at"] = datetime.now(timezone.utc)

        if result is not None:
            update_fields["result"] = result

        if error is not None:
            update_fields["error"] = error

        # api-service stores the job UUID as ``_id`` (not a separate ``id``
        # field) — see MongoJobRepository._to_document() which sets _id=entity.id.
        jobs.update_one({"_id": job_id}, {"$set": update_fields})
        logger.debug(
            "Updated api-service job %s → status=%s", job_id, status
        )
    except Exception as exc:
        logger.error(
            "Failed to update api-service job %s status to %s: %s",
            job_id,
            status,
            exc,
        )


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------

@celery.task(
    name="ai_worker.jobs.execute",
    bind=True,
    max_retries=0,          # No automatic retries — a failed AI job is a
    acks_late=True,         # terminal state, not a transient error.
    reject_on_worker_lost=True,
)
def execute_ai_job(self, job_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an AI job received from the ``ai.default`` queue.

    Args:
        job_payload: Dict published by ``api-service`` containing::

            {
                "job_id":          "<uuid>",
                "job_type":        "<string>",
                "input_data":      { ... },
                "user_id":         "<string>|null",
                "priority":        5,
                "timeout_seconds": 3600,
            }

    Returns:
        A summary dict ``{"job_id": ..., "status": "completed"|"failed"}``.
    """
    job_id = job_payload.get("job_id", "unknown")
    job_type = job_payload.get("job_type", "unknown")
    input_data = job_payload.get("input_data", {})

    logger.info(
        "Received AI job %s (type=%s) from queue", job_id, job_type
    )

    # Each task invocation gets a fresh in-process JobManager so that the
    # Celery worker process is stateless across tasks.  The JobManager is
    # only used here for its state-machine helpers and to fire the
    # notification event; job persistence happens in api-service MongoDB.
    job_manager = JobManager(event_publisher=JobEventPublisher())

    # Register the job in the local job manager so its lifecycle methods work.
    local_job_id = job_manager.create_job(
        payload=input_data,
        model_id=job_type,
    )

    # ------------------------------------------------------------------
    # Mark running
    # ------------------------------------------------------------------
    job_manager.start_job(local_job_id)
    _update_api_job_status(job_id, "running")

    start_ts = time.monotonic()

    # ------------------------------------------------------------------
    # Execute workload
    # ------------------------------------------------------------------
    runner = PlaceholderWorkloadRunner()
    try:
        result = runner.run(input_data)

        duration_ms = int((time.monotonic() - start_ts) * 1000)
        execution_result = {
            "job_type": job_type,
            "output": result,
            "duration_ms": duration_ms,
        }

        # Complete in local manager → fires notification event
        job_manager.complete_job(local_job_id, execution_result)

        # Write terminal state back to api-service MongoDB
        _update_api_job_status(job_id, "completed", result=execution_result)

        logger.info(
            "AI job %s completed successfully (duration=%dms)",
            job_id,
            duration_ms,
        )
        return {"job_id": job_id, "status": "completed"}

    except NotImplementedError:
        # PlaceholderWorkloadRunner raises NotImplementedError until a real
        # workload is registered.  Treat this as a known, expected failure
        # so the job reaches a clean terminal state rather than being
        # retried or left dangling.
        error_msg = (
            f"AI workload for job_type='{job_type}' is not implemented yet. "
            "Replace PlaceholderWorkloadRunner with a real runner."
        )
        logger.warning("AI job %s → %s", job_id, error_msg)
        _handle_failure(job_manager, local_job_id, job_id, error_msg)
        return {"job_id": job_id, "status": "failed", "error": error_msg}

    except Exception as exc:
        error_msg = f"Unexpected error executing job_type='{job_type}': {exc}"
        logger.exception("AI job %s failed unexpectedly", job_id)
        _handle_failure(job_manager, local_job_id, job_id, error_msg)
        return {"job_id": job_id, "status": "failed", "error": error_msg}


def _handle_failure(
    job_manager: JobManager,
    local_job_id: str,
    api_job_id: str,
    error_msg: str,
) -> None:
    """Mark job as failed in both the local manager and api-service MongoDB."""
    try:
        job_manager.fail_job(local_job_id, error_msg)
    except Exception as exc:
        logger.error(
            "Could not call fail_job on local manager for %s: %s",
            api_job_id,
            exc,
        )
    _update_api_job_status(api_job_id, "failed", error=error_msg)
