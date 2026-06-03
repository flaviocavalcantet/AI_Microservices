"""
Unit tests for the async orchestration layer.

No MongoDB, no Motor, no HuggingFace – everything is stubbed in-memory.
Tests run with pytest-asyncio (pip install pytest-asyncio).

Add to pyproject.toml or pytest.ini:
    [tool.pytest.ini_options]
    asyncio_mode = "auto"
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import pytest

from ai_engine.application.async_orchestrator import AsyncAIJobOrchestrator
from ai_engine.application.base_task import AsyncBaseAITask
from ai_engine.domain.models import AIJob, AIJobResult, AIJobStatus, AIJobType
from ai_engine.domain.repositories import AsyncAIJobRepository
from ai_engine.infrastructure.workers.async_job_worker import AsyncAIJobWorker


# ---------------------------------------------------------------------------
# In-memory async repository stub
# ---------------------------------------------------------------------------

class InMemoryAsyncRepository(AsyncAIJobRepository):
    def __init__(self) -> None:
        self._store: dict[str, AIJob] = {}

    async def save(self, job: AIJob) -> None:
        if job.job_id in self._store:
            raise ValueError(f"Job '{job.job_id}' already exists.")
        self._store[job.job_id] = job

    async def get_by_id(self, job_id: str) -> Optional[AIJob]:
        return self._store.get(job_id)

    async def list_by_status(
        self, status: AIJobStatus, limit: int = 100, offset: int = 0
    ) -> list[AIJob]:
        results = [j for j in self._store.values() if j.status == status]
        results.sort(key=lambda j: j.created_at)
        return results[offset : offset + limit]

    async def update(self, job: AIJob) -> None:
        if job.job_id not in self._store:
            raise ValueError(f"Job '{job.job_id}' not found.")
        self._store[job.job_id] = job


# ---------------------------------------------------------------------------
# Async task stubs
# ---------------------------------------------------------------------------

class AsyncSuccessTask(AsyncBaseAITask):
    job_type = AIJobType.SUMMARIZATION

    async def execute(self, payload: dict[str, Any]) -> AIJobResult:
        return AIJobResult(success=True, data={"summary": "async done"})


class AsyncFailingTask(AsyncBaseAITask):
    job_type = AIJobType.SENTIMENT_ANALYSIS

    async def execute(self, payload: dict[str, Any]) -> AIJobResult:
        return AIJobResult.failure("async model exploded")


class AsyncCrashingTask(AsyncBaseAITask):
    job_type = AIJobType.DATASET_PROFILING

    async def execute(self, payload: dict[str, Any]) -> AIJobResult:
        raise RuntimeError("async hard crash")


class AsyncSlowTask(AsyncBaseAITask):
    """Simulates a long-running task; useful for cancellation tests."""

    job_type = AIJobType.SUMMARIZATION

    async def execute(self, payload: dict[str, Any]) -> AIJobResult:
        await asyncio.sleep(60)  # will be cancelled before this completes
        return AIJobResult(success=True, data={})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_orchestrator(
    repo: InMemoryAsyncRepository,
    tasks: list[AsyncBaseAITask],
) -> AsyncAIJobOrchestrator:
    registry = {t.job_type: t for t in tasks}
    return AsyncAIJobOrchestrator(repository=repo, task_registry=registry)


# ---------------------------------------------------------------------------
# AsyncAIJobOrchestrator tests
# ---------------------------------------------------------------------------

class TestAsyncOrchestratorSubmit:
    async def test_submit_creates_pending_job(self):
        repo = InMemoryAsyncRepository()
        orch = make_orchestrator(repo, [AsyncSuccessTask()])
        job = await orch.submit_job(AIJobType.SUMMARIZATION, {"text": "hello"})
        assert job.status == AIJobStatus.PENDING
        assert await repo.get_by_id(job.job_id) is not None

    async def test_submit_returns_job_with_id(self):
        repo = InMemoryAsyncRepository()
        orch = make_orchestrator(repo, [AsyncSuccessTask()])
        job = await orch.submit_job(AIJobType.SUMMARIZATION, {})
        assert job.job_id


class TestAsyncOrchestratorProcess:
    async def test_successful_job_is_completed(self):
        repo = InMemoryAsyncRepository()
        orch = make_orchestrator(repo, [AsyncSuccessTask()])
        job = await orch.submit_job(AIJobType.SUMMARIZATION, {"text": "hi"})
        processed = await orch.process_job(job.job_id)
        assert processed.status == AIJobStatus.COMPLETED
        assert processed.result.success is True
        assert processed.result.data["summary"] == "async done"

    async def test_task_returning_failure_sets_failed_status(self):
        repo = InMemoryAsyncRepository()
        orch = make_orchestrator(repo, [AsyncFailingTask()])
        job = await orch.submit_job(AIJobType.SENTIMENT_ANALYSIS, {"text": "hi"})
        processed = await orch.process_job(job.job_id)
        assert processed.status == AIJobStatus.FAILED
        assert "async model exploded" in processed.result.error

    async def test_crashing_task_sets_failed_status(self):
        repo = InMemoryAsyncRepository()
        orch = make_orchestrator(repo, [AsyncCrashingTask()])
        job = await orch.submit_job(AIJobType.DATASET_PROFILING, {"data": [{}]})
        processed = await orch.process_job(job.job_id)
        assert processed.status == AIJobStatus.FAILED
        assert "async hard crash" in processed.result.error

    async def test_unknown_job_type_fails_gracefully(self):
        repo = InMemoryAsyncRepository()
        orch = make_orchestrator(repo, [])
        job = await orch.submit_job(AIJobType.SUMMARIZATION, {})
        processed = await orch.process_job(job.job_id)
        assert processed.status == AIJobStatus.FAILED

    async def test_nonexistent_job_id_raises(self):
        repo = InMemoryAsyncRepository()
        orch = make_orchestrator(repo, [AsyncSuccessTask()])
        with pytest.raises(ValueError, match="not found"):
            await orch.process_job("does-not-exist")

    async def test_list_pending_jobs(self):
        repo = InMemoryAsyncRepository()
        orch = make_orchestrator(repo, [AsyncSuccessTask()])
        j1 = await orch.submit_job(AIJobType.SUMMARIZATION, {})
        j2 = await orch.submit_job(AIJobType.SUMMARIZATION, {})
        pending = await orch.list_pending_jobs()
        ids = {j.job_id for j in pending}
        assert j1.job_id in ids
        assert j2.job_id in ids

    async def test_list_pending_pagination(self):
        repo = InMemoryAsyncRepository()
        orch = make_orchestrator(repo, [AsyncSuccessTask()])
        for _ in range(5):
            await orch.submit_job(AIJobType.SUMMARIZATION, {})
        page1 = await orch.list_pending_jobs(limit=3, offset=0)
        page2 = await orch.list_pending_jobs(limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 2
        assert {j.job_id for j in page1}.isdisjoint({j.job_id for j in page2})


class TestAsyncOrchestratorCancel:
    async def test_cancel_pending_job(self):
        repo = InMemoryAsyncRepository()
        orch = make_orchestrator(repo, [AsyncSuccessTask()])
        job = await orch.submit_job(AIJobType.SUMMARIZATION, {})
        cancelled = await orch.cancel_job(job.job_id)
        assert cancelled.status == AIJobStatus.CANCELLED

    async def test_cancel_nonexistent_job_raises(self):
        repo = InMemoryAsyncRepository()
        orch = make_orchestrator(repo, [])
        with pytest.raises(ValueError, match="not found"):
            await orch.cancel_job("ghost-id")


# ---------------------------------------------------------------------------
# AsyncAIJobWorker tests
# ---------------------------------------------------------------------------

class TestAsyncWorker:
    async def test_submit_and_enqueue_returns_pending_job(self):
        repo = InMemoryAsyncRepository()
        orch = make_orchestrator(repo, [AsyncSuccessTask()])
        worker = AsyncAIJobWorker(orch, max_concurrent=2)
        job = await worker.submit_and_enqueue(AIJobType.SUMMARIZATION, {"text": "hi"})
        assert job.status == AIJobStatus.PENDING
        await worker.shutdown()

    async def test_job_completes_after_enqueue(self):
        repo = InMemoryAsyncRepository()
        orch = make_orchestrator(repo, [AsyncSuccessTask()])
        worker = AsyncAIJobWorker(orch, max_concurrent=2)
        job = await worker.submit_and_enqueue(AIJobType.SUMMARIZATION, {"text": "hi"})
        await worker.shutdown()
        completed = await worker.get_job(job.job_id)
        assert completed.status == AIJobStatus.COMPLETED

    async def test_on_complete_hook_is_called(self):
        repo = InMemoryAsyncRepository()
        orch = make_orchestrator(repo, [AsyncSuccessTask()])
        received: list[AIJob] = []

        async def hook(job: AIJob) -> None:
            received.append(job)

        worker = AsyncAIJobWorker(orch, max_concurrent=2, on_complete=hook)
        await worker.submit_and_enqueue(AIJobType.SUMMARIZATION, {"text": "hi"})
        await worker.shutdown()
        assert len(received) == 1
        assert received[0].status == AIJobStatus.COMPLETED

    async def test_semaphore_limits_concurrency(self):
        """Only max_concurrent jobs run simultaneously."""
        repo = InMemoryAsyncRepository()
        running: list[int] = []
        peak: list[int] = []

        class CountingTask(AsyncBaseAITask):
            job_type = AIJobType.SUMMARIZATION

            async def execute(self, payload: dict[str, Any]) -> AIJobResult:
                running.append(1)
                peak.append(len(running))
                await asyncio.sleep(0)  # yield to event loop
                running.pop()
                return AIJobResult(success=True, data={})

        orch = make_orchestrator(repo, [CountingTask()])
        worker = AsyncAIJobWorker(orch, max_concurrent=3)
        for _ in range(6):
            await worker.submit_and_enqueue(AIJobType.SUMMARIZATION, {})
        await worker.shutdown()
        assert max(peak) <= 3

    async def test_cancel_job_removes_task(self):
        repo = InMemoryAsyncRepository()
        orch = make_orchestrator(repo, [AsyncSlowTask()])
        worker = AsyncAIJobWorker(orch, max_concurrent=2)
        job = await worker.submit_and_enqueue(AIJobType.SUMMARIZATION, {})
        await asyncio.sleep(0)  # let the task start
        cancelled = await worker.cancel_job(job.job_id)
        assert cancelled.status == AIJobStatus.CANCELLED
        # Task should be removed from internal tracking after cancellation
        await asyncio.sleep(0)
        assert job.job_id not in worker._tasks


# ---------------------------------------------------------------------------
# AsyncAIJobRepository contract tests (against the in-memory stub)
# ---------------------------------------------------------------------------

class TestAsyncRepositoryContract:
    """
    These tests verify the AsyncAIJobRepository contract.
    Run the same tests against MotorAIJobRepository in an integration
    test that spins up a real (or test-container) MongoDB instance.
    """

    async def test_save_and_get(self):
        repo = InMemoryAsyncRepository()
        job = AIJob(job_type=AIJobType.SUMMARIZATION, payload={"text": "x"})
        await repo.save(job)
        fetched = await repo.get_by_id(job.job_id)
        assert fetched is not None
        assert fetched.job_id == job.job_id

    async def test_duplicate_save_raises(self):
        repo = InMemoryAsyncRepository()
        job = AIJob(job_type=AIJobType.SUMMARIZATION, payload={})
        await repo.save(job)
        with pytest.raises(ValueError, match="already exists"):
            await repo.save(job)

    async def test_get_nonexistent_returns_none(self):
        repo = InMemoryAsyncRepository()
        assert await repo.get_by_id("ghost") is None

    async def test_update_persists_status_change(self):
        repo = InMemoryAsyncRepository()
        job = AIJob(job_type=AIJobType.SUMMARIZATION, payload={})
        await repo.save(job)
        job.mark_running()
        await repo.update(job)
        fetched = await repo.get_by_id(job.job_id)
        assert fetched.status == AIJobStatus.RUNNING

    async def test_update_nonexistent_raises(self):
        repo = InMemoryAsyncRepository()
        job = AIJob(job_type=AIJobType.SUMMARIZATION, payload={})
        with pytest.raises(ValueError, match="not found"):
            await repo.update(job)

    async def test_list_by_status_filters_correctly(self):
        repo = InMemoryAsyncRepository()
        j1 = AIJob(job_type=AIJobType.SUMMARIZATION, payload={})
        j2 = AIJob(job_type=AIJobType.SUMMARIZATION, payload={})
        await repo.save(j1)
        await repo.save(j2)
        j2.mark_running()
        await repo.update(j2)
        pending = await repo.list_by_status(AIJobStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].job_id == j1.job_id
