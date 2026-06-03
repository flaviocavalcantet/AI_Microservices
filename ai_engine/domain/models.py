"""
Domain models for the AI Processing Engine.

Rules:
- No framework imports (Flask, pymongo, etc.)
- All models are plain dataclasses → serialization-friendly
- MongoDB-friendly: _id stored as 'job_id' (str), converted at the repo layer
- Designed to support future AI task expansion via AIJobType enum
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class AIJobType(str, Enum):
    """Supported AI task types. Add new entries here as the engine grows."""

    SUMMARIZATION = "summarization"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    DATASET_PROFILING = "dataset_profiling"


class AIJobStatus(str, Enum):
    """Lifecycle states of a job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Value Objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AIJobResult:
    """
    Immutable result container returned by every AI task.

    Attributes:
        success:    Whether the task completed without errors.
        data:       Task-specific output payload (dict keeps it schema-agnostic).
        error:      Human-readable error description, or None on success.
        metadata:   Optional execution metadata (latency, model version, …).
    """

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AIJobResult":
        return cls(
            success=raw["success"],
            data=raw.get("data", {}),
            error=raw.get("error"),
            metadata=raw.get("metadata", {}),
        )

    @classmethod
    def failure(cls, error: str, metadata: dict[str, Any] | None = None) -> "AIJobResult":
        return cls(success=False, error=error, metadata=metadata or {})


# ---------------------------------------------------------------------------
# Aggregate Root
# ---------------------------------------------------------------------------

@dataclass
class AIJob:
    """
    Central aggregate representing a single AI processing job.

    Lifecycle:
        PENDING → RUNNING → COMPLETED | FAILED | CANCELLED

    Attributes:
        job_id:      Unique identifier (UUID4 string).
        job_type:    What kind of AI task to run.
        status:      Current lifecycle state.
        payload:     Raw input data for the task (text, file path, dataset ref…).
        result:      Populated once the job completes (success or failure).
        created_at:  UTC timestamp of creation.
        updated_at:  UTC timestamp of last state change.
        tags:        Optional labels for filtering/grouping (e.g. tenant, project).
    """

    job_type: AIJobType
    payload: dict[str, Any]
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: AIJobStatus = AIJobStatus.PENDING
    result: AIJobResult | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Domain behaviour
    # ------------------------------------------------------------------

    def mark_running(self) -> None:
        self._require_status(AIJobStatus.PENDING)
        self.status = AIJobStatus.RUNNING
        self.updated_at = datetime.now(timezone.utc)

    def mark_completed(self, result: AIJobResult) -> None:
        self._require_status(AIJobStatus.RUNNING)
        self.status = AIJobStatus.COMPLETED
        self.result = result
        self.updated_at = datetime.now(timezone.utc)

    def mark_failed(self, error: str) -> None:
        self._require_status(AIJobStatus.RUNNING)
        self.status = AIJobStatus.FAILED
        self.result = AIJobResult.failure(error)
        self.updated_at = datetime.now(timezone.utc)

    def cancel(self) -> None:
        if self.status not in (AIJobStatus.PENDING, AIJobStatus.RUNNING):
            raise ValueError(f"Cannot cancel job in status '{self.status}'.")
        self.status = AIJobStatus.CANCELLED
        self.updated_at = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Serialization helpers (used by the repo layer / REST layer)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_type": self.job_type.value,
            "status": self.status.value,
            "payload": self.payload,
            "result": self.result.to_dict() if self.result else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AIJob":
        return cls(
            job_id=raw["job_id"],
            job_type=AIJobType(raw["job_type"]),
            status=AIJobStatus(raw["status"]),
            payload=raw.get("payload", {}),
            result=AIJobResult.from_dict(raw["result"]) if raw.get("result") else None,
            created_at=datetime.fromisoformat(raw["created_at"]),
            updated_at=datetime.fromisoformat(raw["updated_at"]),
            tags=raw.get("tags", {}),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _require_status(self, expected: AIJobStatus) -> None:
        if self.status != expected:
            raise ValueError(
                f"Expected status '{expected.value}', got '{self.status.value}'."
            )
