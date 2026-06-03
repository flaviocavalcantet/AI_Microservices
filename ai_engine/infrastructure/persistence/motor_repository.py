"""
Motor (async MongoDB) repository adapter.

Implements AsyncAIJobRepository using motor.motor_asyncio.
Motor is the officially supported async driver for MongoDB; it exposes
the same API surface as pymongo but all collection methods return
coroutines.

Install:  pip install motor

MongoDB document schema (identical to the sync adapter):
--------------------------------------------------------
{
    "_id":        ObjectId(…),   # internal Mongo id (ignored)
    "job_id":     str,           # UUID-based PK (unique index)
    "job_type":   str,
    "status":     str,
    "payload":    dict,
    "result":     dict | null,
    "created_at": datetime,
    "updated_at": datetime,
    "tags":       dict,
}
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorCollection

from ai_engine.domain.models import AIJob, AIJobStatus
from ai_engine.domain.repositories import AsyncAIJobRepository

logger = logging.getLogger(__name__)


class MotorAIJobRepository(AsyncAIJobRepository):
    """Async MongoDB adapter backed by Motor."""

    def __init__(self, collection: AsyncIOMotorCollection) -> None:
        self._col = collection

    # ------------------------------------------------------------------
    # Lifecycle – call once at startup (e.g. inside create_async_engine)
    # ------------------------------------------------------------------

    async def ensure_indexes(self) -> None:
        """Create necessary indexes.  Safe to call multiple times."""
        await self._col.create_index("job_id", unique=True, background=True)
        await self._col.create_index("status", background=True)
        await self._col.create_index("created_at", background=True)

    # ------------------------------------------------------------------
    # AsyncAIJobRepository interface
    # ------------------------------------------------------------------

    async def save(self, job: AIJob) -> None:
        doc = self._to_doc(job)
        try:
            await self._col.insert_one(doc)
        except Exception as exc:
            # Motor wraps DuplicateKeyError in pymongo.errors – re-raise as
            # ValueError so callers don't need to import pymongo.
            if "duplicate key" in str(exc).lower() or "E11000" in str(exc):
                raise ValueError(f"Job with id '{job.job_id}' already exists.") from exc
            raise

    async def get_by_id(self, job_id: str) -> Optional[AIJob]:
        doc = await self._col.find_one({"job_id": job_id})
        if doc is None:
            return None
        return self._from_doc(doc)

    async def list_by_status(
        self,
        status: AIJobStatus,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AIJob]:
        cursor = (
            self._col.find({"status": status.value})
            .sort("created_at", 1)
            .skip(offset)
            .limit(limit)
        )
        return [self._from_doc(doc) async for doc in cursor]

    async def update(self, job: AIJob) -> None:
        doc = self._to_doc(job)
        result = await self._col.replace_one({"job_id": job.job_id}, doc)
        if result.matched_count == 0:
            raise ValueError(f"Job '{job.job_id}' not found; cannot update.")

    # ------------------------------------------------------------------
    # Private helpers (shared with sync adapter – no I/O)
    # ------------------------------------------------------------------

    @staticmethod
    def _to_doc(job: AIJob) -> dict[str, Any]:
        d = job.to_dict()
        d["created_at"] = datetime.fromisoformat(d["created_at"])
        d["updated_at"] = datetime.fromisoformat(d["updated_at"])
        return d

    @staticmethod
    def _from_doc(doc: dict[str, Any]) -> AIJob:
        raw = dict(doc)
        raw.pop("_id", None)
        for key in ("created_at", "updated_at"):
            val = raw.get(key)
            if hasattr(val, "isoformat"):
                raw[key] = val.isoformat()
        return AIJob.from_dict(raw)
