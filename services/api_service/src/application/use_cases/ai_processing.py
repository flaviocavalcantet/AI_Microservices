"""
AI processing use cases.

These classes form the application layer boundary between the REST
presentation layer and the ai_engine domain / orchestration layer.

Each use case:
- Accepts a validated, typed input object (from the schema layer)
- Delegates to the AIJobWorker (sync) or AsyncAIJobWorker (async) via
  injected worker — never imports Flask or touches HTTP
- Returns a plain dict that the controller can serialize directly
- Is fully unit-testable with a stub worker

Four use cases are defined:
  SubmitSummarizeUseCase  – POST /api/v1/ai/summarize
  SubmitSentimentUseCase  – POST /api/v1/ai/sentiment
  SubmitProfileUseCase    – POST /api/v1/ai/profile
  GetAIJobUseCase         – GET  /api/v1/jobs/{job_id}
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from ai_engine.domain.models import AIJob, AIJobType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Worker protocol — both AIJobWorker and AsyncAIJobWorker satisfy it
# ---------------------------------------------------------------------------

@runtime_checkable
class JobWorkerProtocol(Protocol):
    """Structural interface the use cases depend on.

    Both the synchronous AIJobWorker and the async AsyncAIJobWorker satisfy
    this protocol (sync worker has submit_job + enqueue, not submit_and_enqueue,
    so we define the shared surface here and handle both in the use cases).
    """

    def submit_job_sync(self, job_type: AIJobType, payload: dict, tags: dict) -> AIJob:
        """Submit a job and enqueue it for background processing."""
        ...

    def get_job_sync(self, job_id: str) -> AIJob:
        """Retrieve a job by ID."""
        ...


# ---------------------------------------------------------------------------
# Concrete worker adapter (wraps AIJobWorker's public API)
# ---------------------------------------------------------------------------

class SyncWorkerAdapter:
    """
    Wraps AIJobWorker to expose the surface the use cases expect.

    This adapter eliminates the `worker._orchestrator` private-access
    anti-pattern that existed in the old flask_routes.py.
    """

    def __init__(self, worker) -> None:
        # worker: ai_engine.infrastructure.workers.job_worker.AIJobWorker
        self._worker = worker

    def submit_job_sync(
        self, job_type: AIJobType, payload: dict, tags: dict
    ) -> AIJob:
        job = self._worker._orchestrator.submit_job(job_type, payload, tags)
        self._worker.enqueue(job.job_id)
        return job

    def get_job_sync(self, job_id: str) -> AIJob:
        return self._worker._orchestrator.get_job(job_id)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _job_to_response(job: AIJob, request_base_url: str) -> Dict[str, Any]:
    """Serialize an AIJob into the controller response dict."""
    d = job.to_dict()
    return {
        "job_id": d["job_id"],
        "job_type": d["job_type"],
        "status": d["status"],
        "created_at": d["created_at"],
        "updated_at": d["updated_at"],
        "result": d.get("result"),
        "tags": d.get("tags", {}),
        # Convenience: fully-formed poll URL
        "poll_url": f"{request_base_url.rstrip('/')}/api/v1/jobs/{d['job_id']}",
    }


# ---------------------------------------------------------------------------
# SubmitSummarizeUseCase
# ---------------------------------------------------------------------------

class SubmitSummarizeUseCase:
    """
    Submit a text summarization job.

    Translates the validated SummarizeRequest into an AIJob payload,
    persists it as PENDING, and enqueues it for background execution.
    Returns enough data for the controller to build a 202 response.
    """

    def __init__(self, worker: SyncWorkerAdapter) -> None:
        self._worker = worker

    def execute(
        self,
        text: str,
        max_new_tokens: Optional[int],
        min_new_tokens: Optional[int],
        tags: Optional[Dict[str, str]],
        base_url: str,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"text": text}
        if max_new_tokens is not None:
            payload["max_new_tokens"] = max_new_tokens
        if min_new_tokens is not None:
            payload["min_new_tokens"] = min_new_tokens

        job = self._worker.submit_job_sync(
            job_type=AIJobType.SUMMARIZATION,
            payload=payload,
            tags=tags or {},
        )
        logger.info(
            "Summarization job submitted",
            extra={"job_id": job.job_id, "word_count": len(text.split())},
        )
        return _job_to_response(job, base_url)


# ---------------------------------------------------------------------------
# SubmitSentimentUseCase
# ---------------------------------------------------------------------------

class SubmitSentimentUseCase:
    """
    Submit a sentiment analysis job.

    Translates the validated SentimentRequest into an AIJob payload and
    enqueues it. Returns enough data for a 202 response.
    """

    def __init__(self, worker: SyncWorkerAdapter) -> None:
        self._worker = worker

    def execute(
        self,
        text: str,
        neutral_threshold: Optional[float],
        tags: Optional[Dict[str, str]],
        base_url: str,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"text": text}
        if neutral_threshold is not None:
            payload["neutral_threshold"] = neutral_threshold

        job = self._worker.submit_job_sync(
            job_type=AIJobType.SENTIMENT_ANALYSIS,
            payload=payload,
            tags=tags or {},
        )
        logger.info(
            "Sentiment analysis job submitted",
            extra={"job_id": job.job_id, "char_count": len(text)},
        )
        return _job_to_response(job, base_url)


# ---------------------------------------------------------------------------
# SubmitProfileUseCase
# ---------------------------------------------------------------------------

class SubmitProfileUseCase:
    """
    Submit a dataset profiling job.

    Translates the validated ProfileRequest into an AIJob payload and
    enqueues it. Returns enough data for a 202 response.
    """

    def __init__(self, worker: SyncWorkerAdapter) -> None:
        self._worker = worker

    def execute(
        self,
        data: Any,
        input_type: Optional[str],
        tags: Optional[Dict[str, str]],
        base_url: str,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "data": data,
            "input_type": input_type or "auto",
        }

        job = self._worker.submit_job_sync(
            job_type=AIJobType.DATASET_PROFILING,
            payload=payload,
            tags=tags or {},
        )
        logger.info(
            "Dataset profiling job submitted",
            extra={"job_id": job.job_id},
        )
        return _job_to_response(job, base_url)


# ---------------------------------------------------------------------------
# GetAIJobUseCase
# ---------------------------------------------------------------------------

class GetAIJobUseCase:
    """
    Retrieve an AI job by ID.

    Used by GET /api/v1/jobs/{job_id}. Raises ValueError (→ 404) if the
    job does not exist.
    """

    def __init__(self, worker: SyncWorkerAdapter) -> None:
        self._worker = worker

    def execute(self, job_id: str, base_url: str) -> Dict[str, Any]:
        job = self._worker.get_job_sync(job_id)
        return _job_to_response(job, base_url)
