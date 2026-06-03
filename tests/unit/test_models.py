"""Unit tests for domain models."""

import pytest
from datetime import datetime, timezone

from ai_engine.domain.models import AIJob, AIJobResult, AIJobStatus, AIJobType


class TestAIJobResult:
    def test_failure_factory(self):
        r = AIJobResult.failure("oops")
        assert r.success is False
        assert r.error == "oops"
        assert r.data == {}

    def test_round_trip_serialization(self):
        r = AIJobResult(success=True, data={"summary": "hi"}, metadata={"ms": 10})
        assert AIJobResult.from_dict(r.to_dict()) == r


class TestAIJob:
    def _make_job(self) -> AIJob:
        return AIJob(job_type=AIJobType.SUMMARIZATION, payload={"text": "hello world"})

    def test_initial_status_is_pending(self):
        job = self._make_job()
        assert job.status == AIJobStatus.PENDING

    def test_lifecycle_happy_path(self):
        job = self._make_job()
        job.mark_running()
        assert job.status == AIJobStatus.RUNNING
        result = AIJobResult(success=True, data={"summary": "hi"})
        job.mark_completed(result)
        assert job.status == AIJobStatus.COMPLETED
        assert job.result == result

    def test_mark_running_requires_pending(self):
        job = self._make_job()
        job.mark_running()
        with pytest.raises(ValueError, match="Expected status"):
            job.mark_running()

    def test_mark_failed(self):
        job = self._make_job()
        job.mark_running()
        job.mark_failed("something broke")
        assert job.status == AIJobStatus.FAILED
        assert job.result.success is False
        assert "something broke" in job.result.error

    def test_cancel_from_pending(self):
        job = self._make_job()
        job.cancel()
        assert job.status == AIJobStatus.CANCELLED

    def test_cancel_from_completed_raises(self):
        job = self._make_job()
        job.mark_running()
        job.mark_completed(AIJobResult(success=True))
        with pytest.raises(ValueError):
            job.cancel()

    def test_round_trip_serialization(self):
        job = self._make_job()
        job.mark_running()
        job.mark_completed(AIJobResult(success=True, data={"x": 1}))
        restored = AIJob.from_dict(job.to_dict())
        assert restored.job_id == job.job_id
        assert restored.status == job.status
        assert restored.result.data == {"x": 1}
