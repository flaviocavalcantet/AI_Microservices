"""tests/mongodb/integration/conftest.py

Integration-layer fixtures: mongomock database + concrete repositories.

mongomock provides a fully in-memory MongoDB that accepts the same pymongo
API (queries, updates, indexes, cursors, collation, TTL declarations).
No network, no Docker — fast and deterministic.

Requires:  pip install mongomock
"""

from __future__ import annotations

import pytest

try:
    import mongomock
    MONGOMOCK_AVAILABLE = True
except ImportError:
    MONGOMOCK_AVAILABLE = False

skip_if_no_mongomock = pytest.mark.skipif(
    not MONGOMOCK_AVAILABLE,
    reason="mongomock not installed — run: pip install mongomock",
)

from services.auth_service.src.infrastructure.repositories.mongo_user_repository import (
    MongoUserRepository,
)
from services.auth_service.src.infrastructure.repositories.mongo_refresh_token_repository import (
    MongoRefreshTokenRepository,
)


# ─────────────────────────────────────────────────────────────────────────────
# mongomock database (one clean DB per test function)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def integration_db():
    """Fresh mongomock database dropped after each test."""
    if not MONGOMOCK_AVAILABLE:
        pytest.skip("mongomock not installed")
    client = mongomock.MongoClient()
    db = client["auth_service_test"]
    yield db
    # Clean up every collection to guarantee test isolation
    for name in db.list_collection_names():
        db.drop_collection(name)
    client.close()


# ─────────────────────────────────────────────────────────────────────────────
# Concrete repositories wired to mongomock
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def user_repo(integration_db):
    """MongoUserRepository with indexes initialised against mongomock."""
    repo = MongoUserRepository(integration_db)
    repo.initialize()
    return repo


@pytest.fixture
def token_repo(integration_db):
    """MongoRefreshTokenRepository with indexes initialised against mongomock."""
    repo = MongoRefreshTokenRepository(integration_db)
    repo.initialize()
    return repo
