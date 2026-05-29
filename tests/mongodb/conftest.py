"""tests/mongodb/conftest.py

Shared fixtures for all MongoDB test layers.

Provides:
  - Mock pymongo client, database, and collection objects.
  - Canonical sample domain entities and their raw document representations.
  - A factory helper for building User/RefreshToken variants in tests.

These fixtures are available to every test under tests/mongodb/ without
any explicit import.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, PropertyMock
import uuid

import pytest

from services.auth_service.src.domain.entities.user import User
from services.auth_service.src.domain.entities.refresh_token import RefreshToken


# ─────────────────────────────────────────────
# PyMongo mock primitives
# ─────────────────────────────────────────────

@pytest.fixture
def mock_collection():
    """MagicMock standing in for a pymongo Collection.

    Pre-configured return values match the behaviour expected by
    MongoBaseRepository's CRUD helpers so each test only needs to override
    the specific call it cares about.
    """
    col = MagicMock()
    # replace_one (used by save/upsert)
    col.replace_one.return_value = MagicMock(matched_count=1, upserted_id=None)
    # find_one — returns None by default; override per test
    col.find_one.return_value = None
    # delete_one
    col.delete_one.return_value = MagicMock(deleted_count=1)
    # delete_many
    col.delete_many.return_value = MagicMock(deleted_count=0)
    # update_many
    col.update_many.return_value = MagicMock(modified_count=0)
    # find_one_and_update
    col.find_one_and_update.return_value = None
    # count_documents
    col.count_documents.return_value = 0
    # find — returns an iterable cursor mock
    cursor = MagicMock()
    cursor.__iter__ = MagicMock(return_value=iter([]))
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = cursor
    col.find.return_value = cursor
    # create_indexes — no return value needed
    col.create_indexes.return_value = []
    return col


@pytest.fixture
def mock_db(mock_collection):
    """MagicMock standing in for a pymongo Database.

    ``db["any_name"]`` and ``db.any_name`` both return the same mock_collection
    so that repository code using either accessor gets a consistent object.
    """
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=mock_collection)
    db.name = "auth_service_test"
    return db


@pytest.fixture
def mock_mongo_client(mock_db):
    """MagicMock standing in for a MongoClient."""
    client = MagicMock()
    client.__getitem__ = MagicMock(return_value=mock_db)
    client.admin.command.return_value = {"ok": 1}
    return client


# ─────────────────────────────────────────────
# Domain entity fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def sample_user() -> User:
    """A valid, active User domain entity."""
    now = datetime(2026, 1, 15, 10, 0, 0)
    return User(
        id="user-uuid-0001",
        provider="github",
        provider_user_id="gh-12345",
        email="alice@example.com",
        display_name="Alice Dev",
        roles=["user"],
        is_active=True,
        created_at=now,
        last_login_at=now,
        avatar_url="https://avatars.example.com/alice",
    )


@pytest.fixture
def sample_user_doc(sample_user: User) -> dict:
    """Raw MongoDB document corresponding to sample_user.

    Mirrors exactly what MongoUserRepository._to_document() produces
    plus the ``updated_at`` field stamped by MongoBaseRepository.save().
    """
    return {
        "_id": sample_user.id,
        "provider": sample_user.provider,
        "provider_user_id": sample_user.provider_user_id,
        "email": sample_user.email,
        "display_name": sample_user.display_name,
        "roles": sample_user.roles,
        "is_active": sample_user.is_active,
        "avatar_url": sample_user.avatar_url,
        "last_login_at": sample_user.last_login_at,
        "created_at": sample_user.created_at,
        "updated_at": datetime(2026, 1, 15, 10, 0, 1),
    }


@pytest.fixture
def sample_refresh_token() -> RefreshToken:
    """A valid, non-expired, non-revoked RefreshToken entity."""
    now = datetime(2026, 1, 15, 10, 0, 0)
    return RefreshToken(
        id="token-uuid-0001",
        token_hash="abc123def456" * 4,  # 48-char mock hash
        user_id="user-uuid-0001",
        session_id="session-uuid-0001",
        expires_at=now + timedelta(days=30),
        created_at=now,
        used_at=None,
        revoked_at=None,
        revoked_reason=None,
        replaced_by_id=None,
    )


@pytest.fixture
def sample_token_doc(sample_refresh_token: RefreshToken) -> dict:
    """Raw MongoDB document corresponding to sample_refresh_token."""
    t = sample_refresh_token
    return {
        "_id": t.id,
        "token_hash": t.token_hash,
        "user_id": t.user_id,
        "session_id": t.session_id,
        "expires_at": t.expires_at,
        "created_at": t.created_at,
        "used_at": t.used_at,
        "revoked_at": t.revoked_at,
        "revoked_reason": t.revoked_reason,
        "replaced_by_id": t.replaced_by_id,
        "updated_at": datetime(2026, 1, 15, 10, 0, 1),
    }


# ─────────────────────────────────────────────
# Entity builder helpers
# ─────────────────────────────────────────────

def make_user(
    *,
    id: str | None = None,
    provider: str = "github",
    provider_user_id: str | None = None,
    email: str | None = None,
    display_name: str = "Test User",
    roles: list[str] | None = None,
    is_active: bool = True,
) -> User:
    """Build a User with minimal boilerplate for parametrised tests."""
    uid = id or str(uuid.uuid4())
    return User(
        id=uid,
        provider=provider,
        provider_user_id=provider_user_id or f"puid-{uid[:8]}",
        email=email or f"user-{uid[:8]}@example.com",
        display_name=display_name,
        roles=roles or ["user"],
        is_active=is_active,
        created_at=datetime(2026, 1, 1),
        last_login_at=datetime(2026, 1, 1),
    )


def make_token(
    *,
    user_id: str = "user-uuid-0001",
    session_id: str | None = None,
    ttl_days: int = 30,
    revoked: bool = False,
    expired: bool = False,
) -> RefreshToken:
    """Build a RefreshToken variant for parametrised tests."""
    now = datetime(2026, 1, 15, 10, 0, 0)
    expires = now - timedelta(days=1) if expired else now + timedelta(days=ttl_days)
    tok = RefreshToken(
        id=str(uuid.uuid4()),
        token_hash=str(uuid.uuid4()).replace("-", "") * 2,
        user_id=user_id,
        session_id=session_id or str(uuid.uuid4()),
        expires_at=expires,
        created_at=now,
        used_at=None,
        revoked_at=now if revoked else None,
        revoked_reason="test" if revoked else None,
        replaced_by_id=None,
    )
    return tok
