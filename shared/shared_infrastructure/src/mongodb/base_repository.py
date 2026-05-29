"""shared_infrastructure/mongodb/base_repository.py

Abstract base for every MongoDB repository in the platform.

Provides:
  - Collection access via injected Database handle.
  - Automatic `updated_at` stamping on every write.
  - Consistent RepositoryError wrapping around pymongo exceptions.
  - `ensure_indexes()` called eagerly on first collection access (lazy-once).
  - `initialize()` — explicit startup hook for index creation called by the
    DI wiring layer so indexes are created before the first request arrives.
  - Performance metrics recording via injected MongoConnectionManager.
  - Helpers: _build_sort(), _to_object_id(), pagination wiring.

All concrete repositories (MongoUserRepository, MongoJobRepository …)
inherit from this class.  Domain entities never touch it.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, Tuple, TypeVar

from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

T = TypeVar("T")

logger = logging.getLogger(__name__)

SORT_ASCENDING = 1
SORT_DESCENDING = -1


class RepositoryError(Exception):
    """Wraps any infrastructure-layer persistence failure.

    Domain and application layers catch this; they never catch PyMongoError
    directly, keeping MongoDB concerns isolated to the infrastructure layer.
    """


class DuplicateEntityError(RepositoryError):
    """Raised when a unique-constraint violation is detected."""


class MongoBaseRepository(ABC, Generic[T]):
    """Base class for all MongoDB repositories.

    Subclasses must implement:
        COLLECTION_NAME: str          — MongoDB collection name.
        _to_document(entity) -> dict  — entity → document (for writes).
        _to_entity(document) -> T     — document → entity (for reads).
        ensure_indexes()              — declare collection indexes.

    The database handle is injected; the repository itself is stateless
    beyond holding that reference.

    Optional: pass a MongoConnectionManager to enable per-operation
    performance metric recording.
    """

    COLLECTION_NAME: str = NotImplemented  # override in subclass

    def __init__(self, database: Database, connection_manager=None) -> None:
        """
        Args:
            database: Injected pymongo Database handle.
            connection_manager: Optional MongoConnectionManager.  When supplied,
                each operation latency is recorded via
                ``connection_manager.metrics.record_op()``.
        """
        self._db = database
        self._connection_manager = connection_manager
        self._indexes_ensured = False

    # ── Index initialisation ─────────────────────────────────────────────────

    def initialize(self) -> None:
        """Explicit startup hook: create indexes before the first request.

        Call this from the DI wiring layer (e.g., ``mongo_wiring.py``)
        immediately after constructing the repository so that indexes exist
        before traffic arrives, rather than being created lazily on the first
        operation.

        Idempotent — safe to call multiple times.
        """
        if self._indexes_ensured:
            return
        logger.info(
            "%s.initialize(): creating indexes for collection '%s' …",
            self.__class__.__name__,
            self.COLLECTION_NAME,
        )
        try:
            self.ensure_indexes()
            self._indexes_ensured = True
            logger.info(
                "%s.initialize(): indexes ready for '%s'.",
                self.__class__.__name__,
                self.COLLECTION_NAME,
            )
        except PyMongoError as exc:
            # Log but do not raise — a missing index should not block startup;
            # MongoDB will still accept operations (just without the index).
            logger.error(
                "%s.initialize(): failed to create indexes for '%s': %s",
                self.__class__.__name__,
                self.COLLECTION_NAME,
                exc,
            )

    # ── Collection accessor ──────────────────────────────────────────────────

    @property
    def _collection(self) -> Collection:
        col = self._db[self.COLLECTION_NAME]
        if not self._indexes_ensured:
            # Lazy fallback: ensure indexes on first access if initialize()
            # was never called explicitly.
            self.initialize()
        return col

    # ── Subclass contracts ───────────────────────────────────────────────────

    @abstractmethod
    def _to_document(self, entity: T) -> Dict[str, Any]:
        """Convert domain entity to a MongoDB document dict.

        Must set "_id" to entity.id.
        Must NOT set "updated_at" — the base layer stamps it.
        """

    @abstractmethod
    def _to_entity(self, document: Dict[str, Any]) -> T:
        """Reconstruct domain entity from a MongoDB document."""

    @abstractmethod
    def ensure_indexes(self) -> None:
        """Create or verify collection indexes.

        Called once (either eagerly via initialize() or lazily on first
        collection access).  Use collection.create_index() with
        background=True so it is non-blocking in production.
        """

    # ── Metrics helpers ──────────────────────────────────────────────────────

    def _record_op(self, latency_ms: float, success: bool = True) -> None:
        """Forward operation metrics to the connection manager if available."""
        if self._connection_manager is not None:
            try:
                self._connection_manager.metrics.record_op(latency_ms, success)
            except Exception:
                pass  # metrics are best-effort; never fail an operation for them

    # ── Common CRUD ──────────────────────────────────────────────────────────

    def save(self, entity: T) -> T:
        """Upsert entity.  Sets updated_at automatically."""
        t0 = time.perf_counter()
        try:
            doc = self._to_document(entity)
            doc["updated_at"] = datetime.utcnow()
            entity_id = doc["_id"]

            self._collection.replace_one(
                {"_id": entity_id},
                doc,
                upsert=True,
            )
            logger.debug("%s.save id=%s", self.__class__.__name__, entity_id)
            self._record_op((time.perf_counter() - t0) * 1000, success=True)
            return entity
        except DuplicateKeyError as exc:
            self._record_op((time.perf_counter() - t0) * 1000, success=False)
            raise DuplicateEntityError(
                f"Duplicate key violation in {self.COLLECTION_NAME}: {exc}"
            ) from exc
        except PyMongoError as exc:
            self._record_op((time.perf_counter() - t0) * 1000, success=False)
            raise RepositoryError(
                f"Failed to save document in {self.COLLECTION_NAME}: {exc}"
            ) from exc

    def find_by_id(self, entity_id: str) -> Optional[T]:
        """Return entity or None."""
        t0 = time.perf_counter()
        try:
            doc = self._collection.find_one({"_id": entity_id})
            self._record_op((time.perf_counter() - t0) * 1000, success=True)
            return self._to_entity(doc) if doc else None
        except PyMongoError as exc:
            self._record_op((time.perf_counter() - t0) * 1000, success=False)
            raise RepositoryError(
                f"find_by_id failed in {self.COLLECTION_NAME}: {exc}"
            ) from exc

    def delete(self, entity_id: str) -> bool:
        """Delete by id.  Returns True if a document was removed."""
        t0 = time.perf_counter()
        try:
            result = self._collection.delete_one({"_id": entity_id})
            deleted = result.deleted_count > 0
            self._record_op((time.perf_counter() - t0) * 1000, success=True)
            logger.debug(
                "%s.delete id=%s deleted=%s",
                self.__class__.__name__,
                entity_id,
                deleted,
            )
            return deleted
        except PyMongoError as exc:
            self._record_op((time.perf_counter() - t0) * 1000, success=False)
            raise RepositoryError(
                f"delete failed in {self.COLLECTION_NAME}: {exc}"
            ) from exc

    def exists(self, entity_id: str) -> bool:
        t0 = time.perf_counter()
        try:
            result = (
                self._collection.count_documents({"_id": entity_id}, limit=1) > 0
            )
            self._record_op((time.perf_counter() - t0) * 1000, success=True)
            return result
        except PyMongoError as exc:
            self._record_op((time.perf_counter() - t0) * 1000, success=False)
            raise RepositoryError(
                f"exists check failed in {self.COLLECTION_NAME}: {exc}"
            ) from exc

    # ── Pagination helper ─────────────────────────────────────────────────────

    def _find_paginated(
        self,
        query: Dict[str, Any],
        limit: int,
        offset: int,
        sort_field: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[T], int]:
        """Execute a paginated find query.  Returns (entities, total_count)."""
        t0 = time.perf_counter()
        try:
            direction = SORT_DESCENDING if sort_order == "desc" else SORT_ASCENDING
            total = self._collection.count_documents(query)
            cursor = (
                self._collection.find(query)
                .sort(sort_field, direction)
                .skip(offset)
                .limit(limit)
            )
            entities = [self._to_entity(doc) for doc in cursor]
            self._record_op((time.perf_counter() - t0) * 1000, success=True)
            return entities, total
        except PyMongoError as exc:
            self._record_op((time.perf_counter() - t0) * 1000, success=False)
            raise RepositoryError(
                f"Paginated query failed in {self.COLLECTION_NAME}: {exc}"
            ) from exc

    # ── Partial update helper ─────────────────────────────────────────────────

    def _update_fields(
        self, entity_id: str, fields: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Atomic partial update.  Stamps updated_at.  Returns updated document or None."""
        t0 = time.perf_counter()
        try:
            fields["updated_at"] = datetime.utcnow()
            doc = self._collection.find_one_and_update(
                {"_id": entity_id},
                {"$set": fields},
                return_document=True,  # pymongo ReturnDocument.AFTER
            )
            self._record_op((time.perf_counter() - t0) * 1000, success=True)
            return doc
        except PyMongoError as exc:
            self._record_op((time.perf_counter() - t0) * 1000, success=False)
            raise RepositoryError(
                f"_update_fields failed in {self.COLLECTION_NAME}: {exc}"
            ) from exc
