"""
AI Job Orchestrator – the single point of task dispatch.

Responsibilities:
1. Accept a job submission request and persist the job.
2. Resolve the correct BaseAITask implementation from the registry.
3. Drive the job through its lifecycle (PENDING → RUNNING → COMPLETED/FAILED).
4. Persist state changes via the repository port.

The orchestrator is framework-independent and fully unit-testable by injecting
stub repositories and stub task implementations.
"""

from __future__ import annotations

import logging
from typing import Any

from ai_engine.application.base_task import BaseAITask
from ai_engine.domain.models import AIJob, AIJobResult, AIJobStatus, AIJobType
from ai_engine.domain.repositories import AIJobRepository

logger = logging.getLogger(__name__)


class AIJobOrchestrator:
    """
    Coordinates job lifecycle and delegates to concrete AI tasks.

    Args:
        repository:    Repository port for job persistence.
        task_registry: Mapping of AIJobType → BaseAITask instance.
                       Populated by the DI container / application factory.
    """

    def __init__(
        self,
        repository: AIJobRepository,
        task_registry: dict[AIJobType, BaseAITask],
    ) -> None:
        self._repo = repository
        self._registry = task_registry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit_job(
        self,
        job_type: AIJobType,
        payload: dict[str, Any],
        tags: dict[str, str] | None = None,
    ) -> AIJob:
        """
        Create and persist a new job in PENDING state.

        Returns the AIJob so the caller can expose job_id to the client.
        The actual execution is performed by `process_job`.
        """
        job = AIJob(job_type=job_type, payload=payload, tags=tags or {})
        self._repo.save(job)
        logger.info("Job submitted: job_id=%s type=%s", job.job_id, job.job_type.value)
        return job

    def process_job(self, job_id: str) -> AIJob:
        """
        Execute the job synchronously (called by a background worker or inline).

        Drives the full PENDING → RUNNING → COMPLETED | FAILED lifecycle.
        """
        job = self._load_job(job_id)

        try:
            task = self._resolve_task(job.job_type)
            task.validate_payload(job.payload)

            job.mark_running()
            self._repo.update(job)
            logger.info("Job started: job_id=%s", job_id)

            result: AIJobResult = task.execute(job.payload)

            if result.success:
                job.mark_completed(result)
                logger.info("Job completed: job_id=%s", job_id)
            else:
                job.mark_failed(result.error or "Task returned failure without a message.")
                logger.warning("Job failed (task error): job_id=%s error=%s", job_id, result.error)

        except ValueError as exc:
            self._fail_job(job, str(exc))
            logger.warning("Job failed (validation): job_id=%s error=%s", job_id, exc)
        except Exception as exc:  # noqa: BLE001
            self._fail_job(job, f"Unexpected error: {exc}")
            logger.exception("Job failed (unexpected): job_id=%s", job_id)

        self._repo.update(job)
        return job

    def get_job(self, job_id: str) -> AIJob:
        return self._load_job(job_id)

    def list_pending_jobs(self) -> list[AIJob]:
        return self._repo.list_by_status(AIJobStatus.PENDING)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_job(self, job_id: str) -> AIJob:
        job = self._repo.get_by_id(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")
        return job

    def _resolve_task(self, job_type: AIJobType) -> BaseAITask:
        task = self._registry.get(job_type)
        if task is None:
            raise ValueError(f"No task registered for job type '{job_type.value}'.")
        return task

    def _fail_job(self, job: AIJob, error: str) -> None:
        """Safe failure that handles jobs not yet in RUNNING state."""
        if job.status == AIJobStatus.PENDING:
            job.mark_running()
        job.mark_failed(error)
