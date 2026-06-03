"""
Async AI Job Orchestrator – asyncio-native counterpart to AIJobOrchestrator.

Responsibilities (identical to the sync orchestrator, all awaited):
1. Accept a job submission request and persist the job.
2. Resolve the correct AsyncBaseAITask from the registry.
3. Drive the job through PENDING → RUNNING → COMPLETED | FAILED.
4. Persist state changes via the async repository port.

Design decisions:
- submit_job is async because the repository save is awaited.
- process_job is async; the worker awaits it directly on the event loop,
  eliminating the ThreadPoolExecutor entirely.
- The orchestrator remains framework-independent and fully unit-testable
  by injecting an InMemoryAsyncRepository and stub task implementations.
- The sync AIJobOrchestrator is completely untouched; both coexist.
"""

from __future__ import annotations

import logging
from typing import Any

from ai_engine.application.base_task import AsyncBaseAITask
from ai_engine.domain.models import AIJob, AIJobResult, AIJobStatus, AIJobType
from ai_engine.domain.repositories import AsyncAIJobRepository

logger = logging.getLogger(__name__)


class AsyncAIJobOrchestrator:
    """
    Asyncio-native job lifecycle coordinator.

    Args:
        repository:    Async repository port for job persistence.
        task_registry: Mapping of AIJobType → AsyncBaseAITask instance.
                       Populated by create_async_engine().
    """

    def __init__(
        self,
        repository: AsyncAIJobRepository,
        task_registry: dict[AIJobType, AsyncBaseAITask],
    ) -> None:
        self._repo = repository
        self._registry = task_registry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def submit_job(
        self,
        job_type: AIJobType,
        payload: dict[str, Any],
        tags: dict[str, str] | None = None,
    ) -> AIJob:
        """
        Create and persist a new job in PENDING state.

        Returns the AIJob so the caller can expose job_id to the client.
        The actual execution is triggered separately via process_job().
        """
        job = AIJob(job_type=job_type, payload=payload, tags=tags or {})
        await self._repo.save(job)
        logger.info("Job submitted: job_id=%s type=%s", job.job_id, job.job_type.value)
        return job

    async def process_job(self, job_id: str) -> AIJob:
        """
        Execute the job as a coroutine.

        Drives the full PENDING → RUNNING → COMPLETED | FAILED lifecycle.
        Called directly by AsyncAIJobWorker on the event loop – no thread
        pool involved.
        """
        job = await self._load_job(job_id)

        try:
            task = self._resolve_task(job.job_type)
            await task.validate_payload(job.payload)

            job.mark_running()
            await self._repo.update(job)
            logger.info("Job started: job_id=%s", job_id)

            result: AIJobResult = await task.execute(job.payload)

            if result.success:
                job.mark_completed(result)
                logger.info("Job completed: job_id=%s", job_id)
            else:
                job.mark_failed(result.error or "Task returned failure without a message.")
                logger.warning(
                    "Job failed (task error): job_id=%s error=%s", job_id, result.error
                )

        except ValueError as exc:
            await self._fail_job(job, str(exc))
            logger.warning("Job failed (validation): job_id=%s error=%s", job_id, exc)
        except Exception as exc:  # noqa: BLE001
            await self._fail_job(job, f"Unexpected error: {exc}")
            logger.exception("Job failed (unexpected): job_id=%s", job_id)

        await self._repo.update(job)
        return job

    async def get_job(self, job_id: str) -> AIJob:
        return await self._load_job(job_id)

    async def list_pending_jobs(
        self, limit: int = 100, offset: int = 0
    ) -> list[AIJob]:
        return await self._repo.list_by_status(
            AIJobStatus.PENDING, limit=limit, offset=offset
        )

    async def cancel_job(self, job_id: str) -> AIJob:
        """
        Cancel a PENDING or RUNNING job.

        Marks the job as CANCELLED and persists the state change.
        Note: for RUNNING jobs this is a best-effort soft cancel – it marks
        the record but cannot interrupt an already-executing coroutine.
        Callers that need hard cancellation should hold the asyncio.Task
        reference and cancel it directly.
        """
        job = await self._load_job(job_id)
        job.cancel()
        await self._repo.update(job)
        logger.info("Job cancelled: job_id=%s", job_id)
        return job

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _load_job(self, job_id: str) -> AIJob:
        job = await self._repo.get_by_id(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")
        return job

    def _resolve_task(self, job_type: AIJobType) -> AsyncBaseAITask:
        task = self._registry.get(job_type)
        if task is None:
            raise ValueError(f"No task registered for job type '{job_type.value}'.")
        return task

    async def _fail_job(self, job: AIJob, error: str) -> None:
        """Safe failure that handles jobs not yet in RUNNING state."""
        if job.status == AIJobStatus.PENDING:
            job.mark_running()
        job.mark_failed(error)
