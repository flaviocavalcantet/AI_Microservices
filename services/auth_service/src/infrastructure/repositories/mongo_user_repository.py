"""MongoDB implementation of IUserRepository.

Document schema (collection: users):
{
    "_id":               "uuid-string",
    "provider":          "github" | "local",
    "provider_user_id":  "12345"  | "<username>",
    "email":             "user@example.com",
    "display_name":      "John Doe",
    "username":          "johndoe",          # local-auth users only
    "password_hash":     "$2b$12$...",        # local-auth users only
    "roles":             ["user"],
    "is_active":         true,
    "avatar_url":        "https://…",
    "last_login_at":     ISODate,
    "created_at":        ISODate,
    "updated_at":        ISODate
}

Indexes:
  1. Unique: (provider, provider_user_id)  — primary identity lookup
  2. Unique sparse: email                  — secondary lookup
  3. is_active, created_at                 — admin listing
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo import ASCENDING, IndexModel
from pymongo.database import Database

from services.auth_service.src.domain.entities.user import User
from services.auth_service.src.application.ports.interfaces import IUserRepository
from services.auth_service.src.domain.exceptions.auth_errors import UserNotFoundError
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

    # ── Indexes ──────────────────────────────────────────────────────────────

    def ensure_indexes(self) -> None:
        indexes = [
            IndexModel(
                [("provider", ASCENDING), ("provider_user_id", ASCENDING)],
                unique=True,
                name="idx_provider_identity",
                background=True,
            ),
            IndexModel(
                [("email", ASCENDING)],
                unique=True,
                name="idx_email",
                background=True,
                collation={"locale": "en", "strength": 2},
            ),
            IndexModel(
                [("is_active", ASCENDING), ("created_at", ASCENDING)],
                name="idx_active_created",
                background=True,
            ),
        ]
        self._db[self.COLLECTION_NAME].create_indexes(indexes)
        logger.info("users collection indexes ensured.")

    # ── IUserRepository ───────────────────────────────────────────────────────

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

    def find_by_username(self, username: str) -> Optional[User]:
        """Look up a local-auth user by username (stored as provider_user_id)."""
        try:
            doc = self._collection.find_one(
                {"provider": "local", "provider_user_id": username.lower()},
            )
            return self._to_entity(doc) if doc else None
        except Exception as exc:
            raise RepositoryError(f"find_by_username failed: {exc}") from exc

    def list_all(self) -> List[User]:
        try:
            docs = self._collection.find({}, sort=[("created_at", ASCENDING)])
            return [self._to_entity(doc) for doc in docs]
        except Exception as exc:
            raise RepositoryError(f"list_all failed: {exc}") from exc

    def update_roles(self, user_id: str, roles: List[str]) -> User:
        try:
            result = self._collection.find_one_and_update(
                {"_id": user_id},
                {"$set": {"roles": roles, "updated_at": datetime.now(timezone.utc)}},
                return_document=True,
            )
            if result is None:
                raise UserNotFoundError(user_id)
            return self._to_entity(result)
        except UserNotFoundError:
            raise
        except Exception as exc:
            raise RepositoryError(f"update_roles failed: {exc}") from exc

    # ── Document mapping ──────────────────────────────────────────────────────

    def _to_document(self, entity: User) -> Dict[str, Any]:
        doc: Dict[str, Any] = {
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
        }
        if entity.username is not None:
            doc["username"] = entity.username
        if entity.password_hash is not None:
            doc["password_hash"] = entity.password_hash
        return doc

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
            created_at=document.get("created_at", datetime.now(timezone.utc)),
            username=document.get("username"),
            password_hash=document.get("password_hash"),
        )
