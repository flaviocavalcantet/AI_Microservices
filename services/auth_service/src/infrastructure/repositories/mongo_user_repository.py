"""infrastructure/persistence/mongodb/user_repository.py  (auth_service)

Production MongoDB implementation of IUserRepository.

Document schema (collection: users):
{
    "_id":               "uuid-string",          # = User.id
    "provider":          "github",
    "provider_user_id":  "12345",
    "email":             "user@example.com",
    "display_name":      "John Doe",
    "roles":             ["user"],
    "is_active":         true,
    "avatar_url":        "https://…",
    "last_login_at":     ISODate,
    "created_at":        ISODate,
    "updated_at":        ISODate
}

Indexes:
  1. Unique: (provider, provider_user_id)  — primary OAuth identity lookup
  2. Unique: email                          — secondary lookup (sparse for multi-provider)
  3. is_active, created_at                 — admin / list queries
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from pymongo import ASCENDING, IndexModel
from pymongo.database import Database

from .....domain.entities.user import User
from .....application.ports.interfaces import IUserRepository
from shared.shared_infrastructure.src.mongodb.base_repository import (
    MongoBaseRepository,
    RepositoryError,
)

logger = logging.getLogger(__name__)


class MongoUserRepository(MongoBaseRepository[User], IUserRepository):
    """Persists User domain entities to MongoDB."""

    COLLECTION_NAME = "users"

    def __init__(self, database: Database, connection_manager=None) -> None:
        super().__init__(database, connection_manager=connection_manager)

    # ── Index declaration ────────────────────────────────────────────────────

    def ensure_indexes(self) -> None:
        """Declare all indexes for the users collection.

        Idempotent — safe to call on every startup.
        """
        indexes = [
            # Primary OAuth identity — unique composite
            IndexModel(
                [("provider", ASCENDING), ("provider_user_id", ASCENDING)],
                unique=True,
                name="idx_provider_identity",
                background=True,
            ),
            # Email lookup — unique, case-insensitive collation
            IndexModel(
                [("email", ASCENDING)],
                unique=True,
                name="idx_email",
                background=True,
                collation={"locale": "en", "strength": 2},  # case-insensitive
            ),
            # Active-user listing
            IndexModel(
                [("is_active", ASCENDING), ("created_at", ASCENDING)],
                name="idx_active_created",
                background=True,
            ),
        ]
        self._db[self.COLLECTION_NAME].create_indexes(indexes)
        logger.info("users collection indexes ensured.")

    # ── IUserRepository implementation ───────────────────────────────────────

    def find_by_provider(self, provider: str, provider_user_id: str) -> Optional[User]:
        try:
            doc = self._collection.find_one(
                {"provider": provider, "provider_user_id": provider_user_id}
            )
            return self._to_entity(doc) if doc else None
        except Exception as exc:
            raise RepositoryError(f"find_by_provider failed: {exc}") from exc

    def find_by_email(self, email: str) -> Optional[User]:
        try:
            doc = self._collection.find_one(
                {"email": email},
                collation={"locale": "en", "strength": 2},
            )
            return self._to_entity(doc) if doc else None
        except Exception as exc:
            raise RepositoryError(f"find_by_email failed: {exc}") from exc

    # ── Document mapping ─────────────────────────────────────────────────────

    def _to_document(self, entity: User) -> Dict[str, Any]:
        return {
            "_id": entity.id,
            "provider": entity.provider,
            "provider_user_id": entity.provider_user_id,
            "email": entity.email,
            "display_name": entity.display_name,
            "roles": entity.roles,
            "is_active": entity.is_active,
            "avatar_url": entity.avatar_url,
            "last_login_at": entity.last_login_at,
            "created_at": entity.created_at,
            # updated_at is stamped by MongoBaseRepository.save()
        }

    def _to_entity(self, document: Dict[str, Any]) -> User:
        return User(
            id=document["_id"],
            provider=document["provider"],
            provider_user_id=document["provider_user_id"],
            email=document["email"],
            display_name=document["display_name"],
            roles=document.get("roles", ["user"]),
            is_active=document.get("is_active", True),
            avatar_url=document.get("avatar_url"),
            last_login_at=document.get("last_login_at"),
            created_at=document.get("created_at", datetime.utcnow()),
        )
