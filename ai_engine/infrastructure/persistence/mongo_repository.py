"""
MongoDB repository adapter.

Implements AIJobRepository using pymongo.
Translates between domain AIJob objects and MongoDB documents.

MongoDB document schema
-----------------------
{
    "_id": ObjectId(…),   # internal Mongo id (ignored)
    "job_id": str,        # our UUID-based PK (unique index)
    "job_type": str,
    "status": str,
    "payload": dict,
    "result": dict | null,
    "created_at": datetime,
    "updated_at": datetime,
    "tags": dict,
}
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from ai_engine.domain.models import AIJob, AIJobStatus
from ai_engine.domain.repositories import AIJobRepository

logger = logging.getLogger(__name__)


class MongoAIJobRepository(AIJobRepository):
    """Concrete MongoDB adapter for AIJob persistence."""

    def __init__(self, collection: Collection) -> None:
        self._col = collection
        self._ensure_indexes()

    # ------------------------------------------------------------------
    # AIJobRepository interface
    # ------------------------------------------------------------------

    def save(self, job: AIJob) -> None:
        doc = self._to_doc(job)
        try:
            self._col.insert_one(doc)
        except DuplicateKeyError:
            raise ValueError(f"Job with id '{job.job_id}' already exists.")

    def get_by_id(self, job_id: str) -> Optional[AIJob]:
        doc = self._col.find_one({"job_id": job_id})
        if doc is None:
            return None
        return self._from_doc(doc)

    def list_by_status(self, status: AIJobStatus) -> list[AIJob]:
        cursor = self._col.find({"status": status.value}).sort("created_at", 1)
        return [self._from_doc(doc) for doc in cursor]

    def update(self, job: AIJob) -> None:
        doc = self._to_doc(job)
        result = self._col.replace_one({"job_id": job.job_id}, doc)
        if result.matched_count == 0:
            raise ValueError(f"Job '{job.job_id}' not found; cannot update.")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_indexes(self) -> None:
        self._col.create_index("job_id", unique=True, background=True)
        self._col.create_index("status", background=True)
        self._col.create_index("created_at", background=True)

    @staticmethod
    def _to_doc(job: AIJob) -> dict[str, Any]:
        d = job.to_dict()
        # Store datetimes as native Python datetime objects so Mongo indexes them properly.
        from datetime import datetime, timezone

        d["created_at"] = datetime.fromisoformat(d["created_at"])
        d["updated_at"] = datetime.fromisoformat(d["updated_at"])
        return d

    @staticmethod
    def _from_doc(doc: dict[str, Any]) -> AIJob:
        raw = dict(doc)
        raw.pop("_id", None)  # strip Mongo internal id
        # Normalise datetimes to ISO strings for from_dict
        for key in ("created_at", "updated_at"):
            val = raw.get(key)
            if hasattr(val, "isoformat"):
                raw[key] = val.isoformat()
        return AIJob.from_dict(raw)
