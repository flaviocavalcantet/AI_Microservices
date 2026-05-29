"""domain/repositories/ai_processing_result_repository.py  (ai_worker)

Domain-layer repository interface for AIProcessingResult.
Framework-independent — pure Python ABC.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from ..entities.ai_processing_result import AIProcessingResult


class IAIProcessingResultRepository(ABC):
    """Contract for persisting and querying AIProcessingResult entities."""

    @abstractmethod
    def save(self, result: AIProcessingResult) -> AIProcessingResult:
        """Insert or upsert a result document."""

    @abstractmethod
    def find_by_id(self, result_id: str) -> Optional[AIProcessingResult]:
        """Return result by its own id, or None."""

    @abstractmethod
    def find_by_job_id(self, job_id: str) -> List[AIProcessingResult]:
        """Return all result attempts for a job (ordered by created_at asc)."""

    @abstractmethod
    def find_latest_by_job_id(self, job_id: str) -> Optional[AIProcessingResult]:
        """Return the most recent result for a job, or None."""

    @abstractmethod
    def find_by_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[AIProcessingResult], int]:
        """Return paginated results for a user. Returns (results, total_count)."""

    @abstractmethod
    def find_by_model(
        self,
        model_name: str,
        model_version: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[AIProcessingResult], int]:
        """Results filtered by model name/version — for model analytics."""

    @abstractmethod
    def find_by_input_hash(self, input_hash: str) -> Optional[AIProcessingResult]:
        """Exact deduplication lookup — returns the most recent success for this input."""

    @abstractmethod
    def delete(self, result_id: str) -> bool:
        """Delete result by id. Returns True if deleted."""

    @abstractmethod
    def count_by_job(self, job_id: str) -> int:
        """How many result attempts exist for this job."""
