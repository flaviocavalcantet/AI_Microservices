"""
Background job worker.

Uses Python's ThreadPoolExecutor for async job execution within a single
process. Can be replaced with Celery, RQ, or any task queue in the future
without changing the orchestrator or domain layers.

Future event-driven hook:
    After a job transitions to COMPLETED / FAILED, publish an event to a
    message broker by calling an injected `event_publisher.publish(event)`.
    The stub is already wired; just inject a real publisher.
"""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable

from ai_engine.application.orchestrator import AIJobOrchestrator
from ai_engine.domain.models import AIJob

logger = logging.getLogger(__name__)


class AIJobWorker:
    """
    Thin async wrapper around the orchestrator.

    Submits jobs to a thread pool so Flask endpoints can return a 202
    immediately while processing continues in the background.
    """

    def __init__(
        self,
        orchestrator: AIJobOrchestrator,
        max_workers: int = 4,
        on_complete: Callable[[AIJob], None] | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._on_complete = on_complete  # hook for event publishing

    def enqueue(self, job_id: str) -> Future:
        """
        Submit job_id for async processing.

        Returns a concurrent.futures.Future for the caller to optionally await.
        """
        future = self._executor.submit(self._run, job_id)
        return future

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)

    # ------------------------------------------------------------------

    def _run(self, job_id: str) -> AIJob:
        try:
            job = self._orchestrator.process_job(job_id)
            if self._on_complete:
                try:
                    self._on_complete(job)
                except Exception:  # noqa: BLE001
                    logger.exception("on_complete hook failed for job_id=%s", job_id)
            return job
        except Exception:  # noqa: BLE001
            logger.exception("Worker failed for job_id=%s", job_id)
            raise
