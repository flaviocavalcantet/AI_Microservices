"""tests/mongodb/integration/test_mongo_wiring.py

Layer 4 — wire_mongo() integration tests against mongomock.

Verifies that the DI wiring function:
  - Registers both concrete repositories in the container.
  - Calls initialize() on each repo (eager index creation).
  - Registers mongo_manager when provided.
  - teardown_mongo() calls disconnect on the manager.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.auth_service.src.container import ServiceContainer
from services.auth_service.src.infrastructure.repositories.mongo_wiring import (
    teardown_mongo,
    wire_mongo,
)
from services.auth_service.src.infrastructure.repositories.mongo_user_repository import (
    MongoUserRepository,
)
from services.auth_service.src.infrastructure.repositories.mongo_refresh_token_repository import (
    MongoRefreshTokenRepository,
)
from tests.mongodb.integration.conftest import skip_if_no_mongomock


pytestmark = [pytest.mark.integration, pytest.mark.mongodb, skip_if_no_mongomock]


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def container():
    return ServiceContainer()


@pytest.fixture
def mock_manager():
    mgr = MagicMock()
    mgr.health_status.return_value = {"mongodb": {"status": "healthy"}}
    return mgr


# ─────────────────────────────────────────────────────────────────────────────
# wire_mongo
# ─────────────────────────────────────────────────────────────────────────────

class TestWireMongo:
    def test_registers_user_repository(self, container, integration_db):
        wire_mongo(container, integration_db)
        assert container.has_service("user_repository")

    def test_registers_refresh_token_repository(self, container, integration_db):
        wire_mongo(container, integration_db)
        assert container.has_service("refresh_token_repository")

    def test_resolved_user_repo_is_correct_type(self, container, integration_db):
        wire_mongo(container, integration_db)
        repo = container.resolve("user_repository")
        assert isinstance(repo, MongoUserRepository)

    def test_resolved_token_repo_is_correct_type(self, container, integration_db):
        wire_mongo(container, integration_db)
        repo = container.resolve("refresh_token_repository")
        assert isinstance(repo, MongoRefreshTokenRepository)

    def test_indexes_are_created_on_users_collection(self, container, integration_db):
        wire_mongo(container, integration_db)
        # After wiring, the users collection must have indexes beyond the default _id
        indexes = list(integration_db["users"].list_indexes())
        assert len(indexes) > 1  # at minimum: _id + our 3 custom indexes

    def test_indexes_are_created_on_refresh_tokens_collection(self, container, integration_db):
        wire_mongo(container, integration_db)
        indexes = list(integration_db["refresh_tokens"].list_indexes())
        assert len(indexes) > 1

    def test_registers_mongo_manager_when_provided(
        self, container, integration_db, mock_manager
    ):
        wire_mongo(container, integration_db, connection_manager=mock_manager)
        assert container.has_service("mongo_manager")
        assert container.resolve("mongo_manager") is mock_manager

    def test_does_not_register_mongo_manager_when_not_provided(
        self, container, integration_db
    ):
        wire_mongo(container, integration_db, connection_manager=None)
        assert not container.has_service("mongo_manager")

    def test_wire_mongo_is_idempotent(self, container, integration_db):
        """Calling wire_mongo twice should not raise."""
        wire_mongo(container, integration_db)
        wire_mongo(container, integration_db)  # should not raise
        assert container.has_service("user_repository")

    def test_repos_have_indexes_ensured_after_wiring(self, container, integration_db):
        wire_mongo(container, integration_db)
        repo = container.resolve("user_repository")
        assert repo._indexes_ensured is True

    def test_token_repo_has_indexes_ensured_after_wiring(self, container, integration_db):
        wire_mongo(container, integration_db)
        repo = container.resolve("refresh_token_repository")
        assert repo._indexes_ensured is True


# ─────────────────────────────────────────────────────────────────────────────
# Repos are functional after wiring (smoke test)
# ─────────────────────────────────────────────────────────────────────────────

class TestWiredReposFunctionality:
    def test_wired_user_repo_can_save_and_find(self, container, integration_db):
        from tests.mongodb.conftest import make_user
        wire_mongo(container, integration_db)
        repo = container.resolve("user_repository")
        user = make_user(email="wired@example.com")
        repo.save(user)
        found = repo.find_by_id(user.id)
        assert found is not None
        assert found.email == "wired@example.com"

    def test_wired_token_repo_can_save_and_find(self, container, integration_db):
        from tests.mongodb.conftest import make_token
        wire_mongo(container, integration_db)
        repo = container.resolve("refresh_token_repository")
        token = make_token()
        repo.save(token)
        found = repo.find_by_hash(token.token_hash)
        assert found is not None
        assert found.id == token.id


# ─────────────────────────────────────────────────────────────────────────────
# teardown_mongo
# ─────────────────────────────────────────────────────────────────────────────

class TestTeardownMongo:
    def test_calls_disconnect_on_manager(
        self, container, integration_db, mock_manager
    ):
        wire_mongo(container, integration_db, connection_manager=mock_manager)
        teardown_mongo(container)
        mock_manager.disconnect.assert_called_once()

    def test_teardown_is_safe_when_no_mongo_manager_registered(self, container):
        teardown_mongo(container)  # must not raise

    def test_teardown_is_safe_when_disconnect_raises(
        self, container, integration_db
    ):
        mgr = MagicMock()
        mgr.disconnect.side_effect = Exception("network gone")
        wire_mongo(container, integration_db, connection_manager=mgr)
        teardown_mongo(container)  # must not propagate exception
