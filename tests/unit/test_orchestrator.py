"""Unit tests for the orchestrator with in-memory stubs (no MongoDB)."""

from __future__ import annotations

import pytest
from typing import Optional

from ai_engine.application.orchestrator import AIJobOrchestrator
from ai_engine.application.base_task import BaseAITask
from ai_engine.domain.models import AIJob, AIJobResult, AIJobStatus, AIJobType
from ai_engine.domain.repositories import AIJobRepository


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class InMemoryRepository(AIJobRepository):
    def __init__(self):
        self._store: dict[str, AIJob] = {}

    def save(self, job: AIJob) -> None:
        self._store[job.job_id] = job

    def get_by_id(self, job_id: str) -> Optional[AIJob]:
        return self._store.get(job_id)

    def list_by_status(self, status: AIJobStatus) -> list[AIJob]:
        return [j for j in self._store.values() if j.status == status]

    def update(self, job: AIJob) -> None:
        self._store[job.job_id] = job


class SuccessTask(BaseAITask):
    job_type = AIJobType.SUMMARIZATION

    def execute(self, payload):
        return AIJobResult(success=True, data={"summary": "done"})


class FailingTask(BaseAITask):
    job_type = AIJobType.SENTIMENT_ANALYSIS

    def execute(self, payload):
        return AIJobResult.failure("model exploded")


class CrashingTask(BaseAITask):
    job_type = AIJobType.DATASET_PROFILING

    def execute(self, payload):
        raise RuntimeError("hard crash")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def repo():
    return InMemoryRepository()


def make_orchestrator(repo, tasks):
    registry = {t.job_type: t for t in tasks}
    return AIJobOrchestrator(repository=repo, task_registry=registry)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestOrchestratorSubmit:
    def test_submit_creates_pending_job(self, repo):
        orch = make_orchestrator(repo, [SuccessTask()])
        job = orch.submit_job(AIJobType.SUMMARIZATION, {"text": "hello"})
        assert job.status == AIJobStatus.PENDING
        assert repo.get_by_id(job.job_id) is not None

    def test_submit_returns_job_with_id(self, repo):
        orch = make_orchestrator(repo, [SuccessTask()])
        job = orch.submit_job(AIJobType.SUMMARIZATION, {})
        assert job.job_id


class TestOrchestratorProcess:
    def test_successful_job_is_completed(self, repo):
        orch = make_orchestrator(repo, [SuccessTask()])
        job = orch.submit_job(AIJobType.SUMMARIZATION, {"text": "hi"})
        processed = orch.process_job(job.job_id)
        assert processed.status == AIJobStatus.COMPLETED
        assert processed.result.success is True
        assert processed.result.data["summary"] == "done"

    def test_task_returning_failure_sets_failed_status(self, repo):
        orch = make_orchestrator(repo, [FailingTask()])
        job = orch.submit_job(AIJobType.SENTIMENT_ANALYSIS, {"text": "hi"})
        processed = orch.process_job(job.job_id)
        assert processed.status == AIJobStatus.FAILED
        assert "model exploded" in processed.result.error

    def test_crashing_task_sets_failed_status(self, repo):
        orch = make_orchestrator(repo, [CrashingTask()])
        job = orch.submit_job(AIJobType.DATASET_PROFILING, {"data": [{}]})
        processed = orch.process_job(job.job_id)
        assert processed.status == AIJobStatus.FAILED
        assert "hard crash" in processed.result.error

    def test_unknown_job_type_raises(self, repo):
        orch = make_orchestrator(repo, [])  # empty registry
        job = orch.submit_job(AIJobType.SUMMARIZATION, {})
        processed = orch.process_job(job.job_id)
        assert processed.status == AIJobStatus.FAILED

    def test_nonexistent_job_id_raises(self, repo):
        orch = make_orchestrator(repo, [SuccessTask()])
        with pytest.raises(ValueError, match="not found"):
            orch.process_job("does-not-exist")

    def test_list_pending_jobs(self, repo):
        orch = make_orchestrator(repo, [SuccessTask()])
        j1 = orch.submit_job(AIJobType.SUMMARIZATION, {})
        j2 = orch.submit_job(AIJobType.SUMMARIZATION, {})
        pending = orch.list_pending_jobs()
        ids = {j.job_id for j in pending}
        assert j1.job_id in ids
        assert j2.job_id in ids
