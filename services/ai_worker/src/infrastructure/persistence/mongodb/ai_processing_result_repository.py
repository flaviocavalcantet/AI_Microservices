"""infrastructure/persistence/mongodb/ai_processing_result_repository.py  (ai_worker)

MongoDB implementation of IAIProcessingResultRepository.

Document schema (collection: ai_processing_results):
{
    "_id":                "uuid-string",
    "job_id":             "uuid-string",           # FK (not enforced at DB level)
    "user_id":            "uuid-string | null",    # denormalised
    "job_type":           "inference",             # denormalised
    "status":             "success",
    "model_name":         "gpt-4o-mini",
    "model_version":      "2024-07-18",
    "input_hash":         "sha256hex | null",      # deduplication key
    "output":             { … },                   # model predictions / labels
    "artifacts": [
        { "type": "file", "key": "s3://…", "mime": "application/json" }
    ],
    "metrics": {
        "accuracy": 0.97,
        "latency_ms": 234
    },
    "metadata": {
        "gpu": "A100", "framework": "torch==2.3.0"
    },
    "error":              "string | null",
    "processing_time_ms": 234,
    "created_at":         ISODate,
    "updated_at":         ISODate
}

Indexes:
  1. (job_id, created_at desc)              — all attempts for a job
  2. (job_id, status)                       — latest-success lookups
  3. (user_id, created_at desc)             — per-user result history
  4. (model_name, model_version, created_at) — model analytics
  5. Sparse unique: input_hash              — deduplication (null ignored)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.database import Database

from ....domain.entities.ai_processing_result import AIProcessingResult
from ....domain.repositories.ai_processing_result_repository import (
    IAIProcessingResultRepository,
)
from shared.shared_infrastructure.src.mongodb.base_repository import (
    MongoBaseRepository,
    RepositoryError,
)

logger = logging.getLogger(__name__)


class MongoAIProcessingResultRepository(
    MongoBaseRepository[AIProcessingResult],
    IAIProcessingResultRepository,
):
    """MongoDB-backed storage for AI job results."""

    COLLECTION_NAME = "ai_processing_results"

    def __init__(self, database: Database) -> None:
        super().__init__(database)

    # ── Indexes ──────────────────────────────────────────────────────────────

    def ensure_indexes(self) -> None:
        indexes = [
            # Primary result lookup by job (chronological attempts)
            IndexModel(
                [("job_id", ASCENDING), ("created_at", DESCENDING)],
                name="idx_job_created",
                background=True,
            ),
            # Filter by job + status (find successful results only)
            IndexModel(
                [("job_id", ASCENDING), ("status", ASCENDING)],
                name="idx_job_status",
                background=True,
            ),
            # Per-user result history
            IndexModel(
                [("user_id", ASCENDING), ("created_at", DESCENDING)],
                name="idx_user_created",
                background=True,
            ),
            # Model-level analytics (performance trends, versioned rollups)
            IndexModel(
                [
                    ("model_name", ASCENDING),
                    ("model_version", ASCENDING),
                    ("created_at", DESCENDING),
                ],
                name="idx_model_version_created",
                background=True,
            ),
            # Deduplication: unique per input hash, but only when hash is set
            IndexModel(
                [("input_hash", ASCENDING)],
                unique=True,
                sparse=True,            # sparse = null values are NOT indexed
                name="idx_input_hash_dedup",
                background=True,
            ),
        ]
        self._db[self.COLLECTION_NAME].create_indexes(indexes)
        logger.info("ai_processing_results collection indexes ensured.")

    # ── IAIProcessingResultRepository ─────────────────────────────────────────

    def find_by_job_id(self, job_id: str) -> List[AIProcessingResult]:
        try:
            docs = (
                self._collection
                .find({"job_id": job_id})
                .sort("created_at", ASCENDING)
            )
            return [self._to_entity(d) for d in docs]
        except Exception as exc:
            raise RepositoryError(f"find_by_job_id failed: {exc}") from exc

    def find_latest_by_job_id(self, job_id: str) -> Optional[AIProcessingResult]:
        try:
            doc = (
                self._collection
                .find({"job_id": job_id})
                .sort("created_at", DESCENDING)
                .limit(1)
            )
            doc = next(doc, None)
            return self._to_entity(doc) if doc else None
        except Exception as exc:
            raise RepositoryError(f"find_latest_by_job_id failed: {exc}") from exc

    def find_by_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[AIProcessingResult], int]:
        return self._find_paginated(
            {"user_id": user_id}, limit, offset, "created_at", "desc"
        )

    def find_by_model(
        self,
        model_name: str,
        model_version: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[AIProcessingResult], int]:
        query: Dict[str, Any] = {"model_name": model_name}
        if model_version:
            query["model_version"] = model_version
        return self._find_paginated(query, limit, offset, "created_at", "desc")

    def find_by_input_hash(self, input_hash: str) -> Optional[AIProcessingResult]:
        """Return the most recent successful result for this exact input, if any."""
        try:
            doc = (
                self._collection
                .find({"input_hash": input_hash, "status": AIProcessingResult.STATUS_SUCCESS})
                .sort("created_at", DESCENDING)
                .limit(1)
            )
            doc = next(doc, None)
            return self._to_entity(doc) if doc else None
        except Exception as exc:
            raise RepositoryError(f"find_by_input_hash failed: {exc}") from exc

    def count_by_job(self, job_id: str) -> int:
        try:
            return self._collection.count_documents({"job_id": job_id})
        except Exception as exc:
            raise RepositoryError(f"count_by_job failed: {exc}") from exc

    # ── Document mapping ─────────────────────────────────────────────────────

    def _to_document(self, entity: AIProcessingResult) -> Dict[str, Any]:
        return {
            "_id": entity.id,
            "job_id": entity.job_id,
            "user_id": entity.user_id,
            "job_type": entity.job_type,
            "status": entity.status,
            "model_name": entity.model_name,
            "model_version": entity.model_version,
            "input_hash": entity.input_hash,
            "output": entity.output,
            "artifacts": entity.artifacts,
            "metrics": entity.metrics,
            "metadata": entity.metadata,
            "error": entity.error,
            "processing_time_ms": entity.processing_time_ms,
            "created_at": entity.created_at,
        }

    def _to_entity(self, document: Dict[str, Any]) -> AIProcessingResult:
        return AIProcessingResult(
            id=document["_id"],
            job_id=document["job_id"],
            user_id=document.get("user_id"),
            job_type=document.get("job_type", "unknown"),
            status=document["status"],
            model_name=document.get("model_name", ""),
            model_version=document.get("model_version", ""),
            input_hash=document.get("input_hash"),
            output=document.get("output", {}),
            artifacts=document.get("artifacts", []),
            metrics=document.get("metrics", {}),
            metadata=document.get("metadata", {}),
            error=document.get("error"),
            processing_time_ms=document.get("processing_time_ms"),
            created_at=document.get("created_at", datetime.utcnow()),
        )
