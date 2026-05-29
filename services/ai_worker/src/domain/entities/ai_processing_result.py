"""domain/entities/ai_processing_result.py  (ai_worker)

Domain entity representing the output of a completed AI inference or
training task.

Design notes:
  - One result per job execution attempt (job_id is NOT unique — retries
    each produce their own result document so the full history is retained).
  - `artifacts` stores output file references (S3 keys, local paths, etc.)
    as a list of dicts; the structure is intentionally flexible to support
    diverse model output formats.
  - `metrics` holds evaluation figures (accuracy, loss, latency_ms …).
  - `metadata` is an open bag for model version, hardware info, etc.
  - The entity has zero framework dependencies.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class AIProcessingResult:
    """Output produced by one AI job execution.

    Attributes:
        id:             UUID string, assigned at creation.
        job_id:         FK to the Job that produced this result.
        user_id:        Denormalised for efficient per-user queries.
        job_type:       Denormalised (inference / training / evaluation …).
        status:         "success" | "partial_success" | "failure".
        model_name:     Model identifier used for inference/training.
        model_version:  Semver or git-sha of the model artifact.
        input_hash:     SHA-256 of canonicalised input_data (for dedup).
        output:         Structured model output (predictions, labels …).
        artifacts:      List of output file references.
        metrics:        Numeric evaluation metrics.
        metadata:       Arbitrary key-value bag (hardware, env, etc.).
        error:          Error detail when status != "success".
        processing_time_ms: Wall-clock execution duration in ms.
        created_at:     UTC timestamp of result creation.
    """

    id: str
    job_id: str
    user_id: Optional[str]
    job_type: str
    status: str                                         # success | partial_success | failure
    model_name: str
    model_version: str
    input_hash: Optional[str]
    output: Dict[str, Any]
    artifacts: List[Dict[str, Any]]
    metrics: Dict[str, float]
    metadata: Dict[str, Any]
    error: Optional[str]
    processing_time_ms: Optional[int]
    created_at: datetime

    # ── Status constants ─────────────────────────────────────────────────────
    STATUS_SUCCESS = "success"
    STATUS_PARTIAL = "partial_success"
    STATUS_FAILURE = "failure"
    VALID_STATUSES = {STATUS_SUCCESS, STATUS_PARTIAL, STATUS_FAILURE}

    # ── Factory ──────────────────────────────────────────────────────────────

    @classmethod
    def create_success(
        cls,
        job_id: str,
        job_type: str,
        model_name: str,
        model_version: str,
        output: Dict[str, Any],
        user_id: Optional[str] = None,
        artifacts: Optional[List[Dict[str, Any]]] = None,
        metrics: Optional[Dict[str, float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        input_hash: Optional[str] = None,
        processing_time_ms: Optional[int] = None,
    ) -> "AIProcessingResult":
        return cls(
            id=str(uuid.uuid4()),
            job_id=job_id,
            user_id=user_id,
            job_type=job_type,
            status=cls.STATUS_SUCCESS,
            model_name=model_name,
            model_version=model_version,
            input_hash=input_hash,
            output=output,
            artifacts=artifacts or [],
            metrics=metrics or {},
            metadata=metadata or {},
            error=None,
            processing_time_ms=processing_time_ms,
            created_at=datetime.utcnow(),
        )

    @classmethod
    def create_failure(
        cls,
        job_id: str,
        job_type: str,
        model_name: str,
        model_version: str,
        error: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        processing_time_ms: Optional[int] = None,
    ) -> "AIProcessingResult":
        return cls(
            id=str(uuid.uuid4()),
            job_id=job_id,
            user_id=user_id,
            job_type=job_type,
            status=cls.STATUS_FAILURE,
            model_name=model_name,
            model_version=model_version,
            input_hash=None,
            output={},
            artifacts=[],
            metrics={},
            metadata=metadata or {},
            error=error,
            processing_time_ms=processing_time_ms,
            created_at=datetime.utcnow(),
        )

    # ── Business logic ───────────────────────────────────────────────────────

    def is_successful(self) -> bool:
        return self.status == self.STATUS_SUCCESS

    def is_valid(self) -> bool:
        if not self.id or not self.job_id or not self.model_name:
            return False
        if self.status not in self.VALID_STATUSES:
            return False
        if self.status == self.STATUS_FAILURE and not self.error:
            return False
        return True

    def add_artifact(self, artifact: Dict[str, Any]) -> None:
        """Append an output file reference post-construction."""
        self.artifacts.append(artifact)

    def record_metric(self, name: str, value: float) -> None:
        self.metrics[name] = value
