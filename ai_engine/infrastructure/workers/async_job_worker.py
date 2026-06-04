"""
Asyncio-native job worker.

Replaces the ThreadPoolExecutor approach with a pure asyncio task pool.
Each enqueued job becomes an asyncio.Task running the AsyncAIJobOrchestrator
coroutine directly on the event loop – no threads involved.

Key differences from the sync AIJobWorker
------------------------------------------
- enqueue()   returns an asyncio.Task instead of a concurrent.futures.Future.
- shutdown()  is a coroutine; it cancels running tasks and awaits their cleanup.
- on_complete receives an awaitable callback (async def) so downstream actions
  (event publishing, notifications) can also be non-blocking.
- cancel_job() delegates to the orchestrator AND cancels the in-flight
  asyncio.Task if one exists, providing true cooperative cancellation.

Concurrency control
-------------------
max_concurrent limits the number of simultaneously running process_job
coroutines via asyncio.Semaphore.  This prevents unbounded parallelism
while keeping everything on the event loop.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from ai_engine.application.async_orchestrator import AsyncAIJobOrchestrator
from ai_engine.domain.models import AIJob, AIJobType

logger = logging.getLogger(__name__)

# Type alias for the optional async completion hook.
AsyncJobCallback = Callable[[AIJob], Awaitable[None]]


class AsyncAIJobWorker:
    """
    Asyncio-native worker that dispatches jobs as coroutines.

    Usage (inside an async context, e.g. FastAPI lifespan or aiohttp):

        worker = AsyncAIJobWorker(orchestrator, max_concurrent=8)
        job = await worker.submit_and_enqueue(AIJobType.SUMMARIZATION, payload)
        # returns immediately; processing runs in the background

        # later:
        job = await worker.get_job(job.job_id)

        # clean shutdown:
        await worker.shutdown()
    """

    def __init__(
        self,
        orchestrator: AsyncAIJobOrchestrator,
        max_concurrent: int = 8,
        on_complete: AsyncJobCallback | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._on_complete = on_complete
        # job_id → running asyncio.Task, for cancellation support
        self._tasks: dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def submit_and_enqueue(
        self,
        job_type: AIJobType,
        payload: dict[str, Any],
        tags: dict[str, str] | None = None,
    ) -> AIJob:
        """
        Persist the job (PENDING) and schedule it for execution.

        Returns immediately with the AIJob so the caller can expose
        job_id to the client (HTTP 202 pattern).
        """
        job = await self._orchestrator.submit_job(job_type, payload, tags)
        self.enqueue(job.job_id)
        return job

    def enqueue(self, job_id: str) -> asyncio.Task:
        """
        Schedule an existing (PENDING) job for async execution.

        Creates an asyncio.Task and stores it for optional cancellation.
        Returns the Task for callers that want to await or inspect it.
        """
        task = asyncio.create_task(
            self._run(job_id),
            name=f"ai-job-{job_id}",
        )
        self._tasks[job_id] = task
        task.add_done_callback(lambda t: self._tasks.pop(job_id, None))
        return task

    async def get_job(self, job_id: str) -> AIJob:
        """Retrieve the current state of a job from the repository."""
        return await self._orchestrator.get_job(job_id)

    async def cancel_job(self, job_id: str) -> AIJob:
        """
        Cancel a job both in storage and as a running asyncio.Task.

        - Marks the job CANCELLED in the repository.
        - If an asyncio.Task is still running for this job, cancels it
          cooperatively (the coroutine will receive CancelledError at its
          next await point).
        """
        job = await self._orchestrator.cancel_job(job_id)

        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            self._tasks.pop(job_id, None)
            logger.info("asyncio.Task cancelled for job_id=%s", job_id)

        return job

    async def list_pending(
        self, limit: int = 100, offset: int = 0
    ) -> list[AIJob]:
        return await self._orchestrator.list_pending_jobs(limit=limit, offset=offset)

    async def shutdown(self, timeout: float = 30.0) -> None:
        """
        Gracefully shut down the worker.

        Waits up to `timeout` seconds for in-flight tasks to complete,
        then cancels any that are still running.
        """
        if not self._tasks:
            return

        logger.info("Shutting down AsyncAIJobWorker (%d tasks in flight)…", len(self._tasks))
        pending = list(self._tasks.values())

        try:
            await asyncio.wait_for(
                asyncio.gather(*pending, return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Shutdown timeout reached; cancelling %d remaining tasks.", len(self._tasks)
            )
            for task in self._tasks.values():
                task.cancel()
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    async def _run(self, job_id: str) -> AIJob:
        """Acquire the concurrency slot, run the orchestrator, fire the hook."""
        async with self._semaphore:
            try:
                job = await self._orchestrator.process_job(job_id)
            except asyncio.CancelledError:
                logger.info("Job coroutine cancelled: job_id=%s", job_id)
                raise
            except Exception:  # noqa: BLE001
                logger.exception("Worker failed for job_id=%s", job_id)
                raise

        if self._on_complete:
            try:
                await self._on_complete(job)
            except Exception:  # noqa: BLE001
                logger.exception("on_complete hook failed for job_id=%s", job_id)

        return job
