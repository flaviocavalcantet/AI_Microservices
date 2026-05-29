"""infrastructure/persistence/mongodb/refresh_token_repository.py  (auth_service)

Production MongoDB implementation of IRefreshTokenRepository.

Document schema (collection: refresh_tokens):
{
    "_id":             "uuid-string",        # = RefreshToken.id
    "token_hash":      "sha256hex",          # indexed unique — lookup key
    "user_id":         "uuid-string",
    "session_id":      "uuid-string",        # token family for reuse detection
    "expires_at":      ISODate,
    "created_at":      ISODate,
    "used_at":         ISODate | null,
    "revoked_at":      ISODate | null,
    "revoked_reason":  "string | null",
    "replaced_by_id":  "uuid-string | null",
    "updated_at":      ISODate
}

Indexes:
  1. Unique: token_hash                              — primary lookup
  2.         session_id, revoked_at                 — family revocation
  3.         user_id, created_at                    — user-scoped queries
  4. TTL:    expires_at (expireAfterSeconds=0)      — auto-delete expired tokens
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from pymongo import ASCENDING, IndexModel
from pymongo.database import Database

from .....domain.entities.refresh_token import RefreshToken
from .....application.ports.interfaces import IRefreshTokenRepository
from shared.shared_infrastructure.src.mongodb.base_repository import (
    MongoBaseRepository,
    RepositoryError,
)

logger = logging.getLogger(__name__)


class MongoRefreshTokenRepository(MongoBaseRepository[RefreshToken], IRefreshTokenRepository):
    """Persists RefreshToken entities to MongoDB with TTL auto-expiry."""

    COLLECTION_NAME = "refresh_tokens"

    def __init__(self, database: Database, connection_manager=None) -> None:
        super().__init__(database, connection_manager=connection_manager)

    # ── Indexes ──────────────────────────────────────────────────────────────

    def ensure_indexes(self) -> None:
        indexes = [
            # Primary lookup by hashed token value
            IndexModel(
                [("token_hash", ASCENDING)],
                unique=True,
                name="idx_token_hash",
                background=True,
            ),
            # Token-family queries (revocation sweep)
            IndexModel(
                [("session_id", ASCENDING), ("revoked_at", ASCENDING)],
                name="idx_session_revoked",
                background=True,
            ),
            # User-scoped history
            IndexModel(
                [("user_id", ASCENDING), ("created_at", ASCENDING)],
                name="idx_user_created",
                background=True,
            ),
            # TTL index — MongoDB deletes documents where expires_at <= now
            IndexModel(
                [("expires_at", ASCENDING)],
                expireAfterSeconds=0,
                name="idx_expires_ttl",
                background=True,
            ),
        ]
        self._db[self.COLLECTION_NAME].create_indexes(indexes)
        logger.info("refresh_tokens collection indexes ensured.")

    # ── IRefreshTokenRepository ───────────────────────────────────────────────

    def find_by_hash(self, token_hash: str) -> Optional[RefreshToken]:
        try:
            doc = self._collection.find_one({"token_hash": token_hash})
            return self._to_entity(doc) if doc else None
        except Exception as exc:
            raise RepositoryError(f"find_by_hash failed: {exc}") from exc

    def find_by_session_id(self, session_id: str) -> List[RefreshToken]:
        try:
            docs = self._collection.find({"session_id": session_id})
            return [self._to_entity(d) for d in docs]
        except Exception as exc:
            raise RepositoryError(f"find_by_session_id failed: {exc}") from exc

    def revoke_session(self, session_id: str, reason: str) -> int:
        """Atomically revoke all active tokens in a session family.

        Returns the number of tokens revoked.
        """
        try:
            now = datetime.utcnow()
            result = self._collection.update_many(
                {"session_id": session_id, "revoked_at": None},
                {"$set": {"revoked_at": now, "revoked_reason": reason, "updated_at": now}},
            )
            count = result.modified_count
            logger.info("Revoked %d tokens for session %s (reason=%s)", count, session_id, reason)
            return count
        except Exception as exc:
            raise RepositoryError(f"revoke_session failed: {exc}") from exc

    def delete_expired(self) -> int:
        """Manual housekeeping — removes already-expired tokens.

        Normally the TTL index handles this automatically; this method
        is useful for immediate clean-up or testing.
        """
        try:
            result = self._collection.delete_many(
                {"expires_at": {"$lte": datetime.utcnow()}}
            )
            return result.deleted_count
        except Exception as exc:
            raise RepositoryError(f"delete_expired failed: {exc}") from exc

    # ── Document mapping ─────────────────────────────────────────────────────

    def _to_document(self, entity: RefreshToken) -> Dict[str, Any]:
        return {
            "_id": entity.id,
            "token_hash": entity.token_hash,
            "user_id": entity.user_id,
            "session_id": entity.session_id,
            "expires_at": entity.expires_at,
            "created_at": entity.created_at,
            "used_at": entity.used_at,
            "revoked_at": entity.revoked_at,
            "revoked_reason": entity.revoked_reason,
            "replaced_by_id": entity.replaced_by_id,
        }

    def _to_entity(self, document: Dict[str, Any]) -> RefreshToken:
        return RefreshToken(
            id=document["_id"],
            token_hash=document["token_hash"],
            user_id=document["user_id"],
            session_id=document["session_id"],
            expires_at=document["expires_at"],
            created_at=document.get("created_at", datetime.utcnow()),
            used_at=document.get("used_at"),
            revoked_at=document.get("revoked_at"),
            revoked_reason=document.get("revoked_reason"),
            replaced_by_id=document.get("replaced_by_id"),
        )
