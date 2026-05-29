"""infrastructure/persistence/mongodb/job_repository.py  (api_service)

FULL production implementation replacing the previous stub.

Document schema (collection: jobs):
{
    "_id":              "uuid-string",
    "user_id":          "uuid-string | null",
    "job_type":         "inference",
    "status":           "pending",
    "priority":         5,
    "input_data":       { … },
    "result":           { … } | null,
    "error":            "string | null",
    "timeout_seconds":  300 | null,
    "started_at":       ISODate | null,
    "completed_at":     ISODate | null,
    "created_at":       ISODate,
    "updated_at":       ISODate
}

Indexes (see ensure_indexes):
  1. (user_id, created_at desc)     — per-user job list, newest first
  2. (status, created_at desc)      — status-based worker queue polling
  3. (user_id, status)              — filtered list queries
  4. (job_type, status)             — analytics / admin queries
  5. (priority desc, created_at)    — priority-aware queue polling
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.database import Database

from ....domain.entities.job import Job
from ....domain.repositories.job_repository import IJobRepository
from shared.shared_infrastructure.src.mongodb.base_repository import (
    MongoBaseRepository,
    RepositoryError,
)

logger = logging.getLogger(__name__)


class MongoJobRepository(MongoBaseRepository[Job], IJobRepository):
    """Full MongoDB implementation of IJobRepository."""

    COLLECTION_NAME = "jobs"

    def __init__(self, database: Database) -> None:
        super().__init__(database)

    # ── Indexes ──────────────────────────────────────────────────────────────

    def ensure_indexes(self) -> None:
        indexes = [
            # Per-user chronological listing (most common API query)
            IndexModel(
                [("user_id", ASCENDING), ("created_at", DESCENDING)],
                name="idx_user_created",
                background=True,
            ),
            # Status-based polling (workers fetch PENDING jobs)
            IndexModel(
                [("status", ASCENDING), ("created_at", DESCENDING)],
                name="idx_status_created",
                background=True,
            ),
            # Combined user + status filter (dashboard)
            IndexModel(
                [("user_id", ASCENDING), ("status", ASCENDING)],
                name="idx_user_status",
                background=True,
            ),
            # Analytics / admin
            IndexModel(
                [("job_type", ASCENDING), ("status", ASCENDING)],
                name="idx_type_status",
                background=True,
            ),
            # Priority queue: highest priority (low int), oldest first
            IndexModel(
                [("priority", ASCENDING), ("created_at", ASCENDING)],
                name="idx_priority_queue",
                background=True,
                partialFilterExpression={"status": "pending"},  # only pending jobs
            ),
        ]
        self._db[self.COLLECTION_NAME].create_indexes(indexes)
        logger.info("jobs collection indexes ensured.")

    # ── IJobRepository implementation ────────────────────────────────────────

    def find_all(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[Job], int]:
        query: Dict[str, Any] = {}
        if user_id:
            query["user_id"] = user_id
        if status:
            query["status"] = status
        if job_type:
            query["job_type"] = job_type
        return self._find_paginated(query, limit, offset, sort_by, sort_order)

    def find_by_status(
        self,
        status: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Job], int]:
        return self._find_paginated(
            {"status": status}, limit, offset, "created_at", "asc"
        )

    def find_by_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Job], int]:
        return self._find_paginated(
            {"user_id": user_id}, limit, offset, "created_at", "desc"
        )

    def update_status(self, job_id: str, status: str) -> Optional[Job]:
        """Targeted partial update — only status + timestamps change."""
        fields: Dict[str, Any] = {"status": status}

        if status == "running":
            fields["started_at"] = datetime.utcnow()
        elif status in ("completed", "failed", "cancelled"):
            fields["completed_at"] = datetime.utcnow()

        doc = self._update_fields(job_id, fields)
        return self._to_entity(doc) if doc else None

    def count(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int:
        try:
            query: Dict[str, Any] = {}
            if user_id:
                query["user_id"] = user_id
            if status:
                query["status"] = status
            return self._collection.count_documents(query)
        except Exception as exc:
            raise RepositoryError(f"count failed: {exc}") from exc

    # ── Document mapping ─────────────────────────────────────────────────────

    def _to_document(self, entity: Job) -> Dict[str, Any]:
        return {
            "_id": entity.id,
            "user_id": entity.user_id,
            "job_type": entity.job_type,
            "status": entity.status,
            "priority": entity.priority,
            "input_data": entity.input_data,
            "result": entity.result,
            "error": entity.error,
            "timeout_seconds": entity.timeout_seconds,
            "started_at": entity.started_at,
            "completed_at": entity.completed_at,
            "created_at": entity.created_at,
        }

    def _to_entity(self, document: Dict[str, Any]) -> Job:
        return Job(
            id=document["_id"],
            user_id=document.get("user_id"),
            job_type=document["job_type"],
            status=document["status"],
            priority=document.get("priority", 5),
            input_data=document.get("input_data", {}),
            result=document.get("result"),
            error=document.get("error"),
            created_at=document.get("created_at", datetime.utcnow()),
            started_at=document.get("started_at"),
            completed_at=document.get("completed_at"),
            timeout_seconds=document.get("timeout_seconds"),
        )
