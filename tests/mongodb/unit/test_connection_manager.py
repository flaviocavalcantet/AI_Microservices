"""tests/mongodb/unit/test_connection_manager.py

Layer 2 — MongoConnectionManager unit tests.

All MongoDB I/O is replaced with MagicMock so these tests run offline
in milliseconds. The retry delay is forced to 0 so the back-off loop
completes instantly.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from shared.shared_infrastructure.src.mongodb.connection import MongoConnectionManager

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

VALID_URI = "mongodb://admin:pass@localhost:27017/db?authSource=admin"


def _manager(max_retries: int = 3, retry_delay: float = 0.0) -> MongoConnectionManager:
    """Build a manager with zero retry delay so tests complete instantly."""
    return MongoConnectionManager(
        uri=VALID_URI,
        max_retries=max_retries,
        retry_delay_seconds=retry_delay,
    )


# ─────────────────────────────────────────────────────────────────────────────
# from_env
# ─────────────────────────────────────────────────────────────────────────────

class TestFromEnv:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_raises_when_uri_env_var_missing(self, monkeypatch):
        monkeypatch.delenv("MONGODB_URI", raising=False)
        with pytest.raises(EnvironmentError, match="MONGODB_URI"):
            MongoConnectionManager.from_env()

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_builds_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("MONGODB_URI", VALID_URI)
        monkeypatch.setenv("MONGODB_MAX_POOL_SIZE", "50")
        monkeypatch.setenv("MONGODB_MAX_RETRIES", "5")
        m = MongoConnectionManager.from_env()
        assert m._client_kwargs["maxPoolSize"] == 50
        assert m._max_retries == 5

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_applies_default_pool_sizes_when_env_absent(self, monkeypatch):
        monkeypatch.setenv("MONGODB_URI", VALID_URI)
        for k in ("MONGODB_MIN_POOL_SIZE", "MONGODB_MAX_POOL_SIZE"):
            monkeypatch.delenv(k, raising=False)
        m = MongoConnectionManager.from_env()
        assert m._client_kwargs["minPoolSize"] == 2
        assert m._client_kwargs["maxPoolSize"] == 20


# ─────────────────────────────────────────────────────────────────────────────
# connect — success path
# ─────────────────────────────────────────────────────────────────────────────

class TestConnectSuccess:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_connect_stores_client_on_success(self):
        m = _manager()
        mock_client = MagicMock()
        mock_client.admin.command.return_value = {"ok": 1}
        with patch(
            "shared.shared_infrastructure.src.mongodb.connection.MongoClient",
            return_value=mock_client,
        ):
            m.connect()
        assert m._client is mock_client

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_connect_increments_success_counter(self):
        m = _manager()
        mock_client = MagicMock()
        mock_client.admin.command.return_value = {"ok": 1}
        with patch(
            "shared.shared_infrastructure.src.mongodb.connection.MongoClient",
            return_value=mock_client,
        ):
            m.connect()
        assert m.metrics.connect_successes == 1
        assert m.metrics.connect_failures == 0

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_connect_is_idempotent_when_already_connected(self):
        m = _manager()
        fake_client = MagicMock()
        fake_client.admin.command.return_value = {"ok": 1}
        with patch(
            "shared.shared_infrastructure.src.mongodb.connection.MongoClient",
            return_value=fake_client,
        ) as MockClient:
            m.connect()
            m.connect()          # second call should be a no-op
            MockClient.assert_called_once()   # MongoClient constructed only once

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_connect_calls_ping_on_admin(self):
        m = _manager()
        mock_client = MagicMock()
        mock_client.admin.command.return_value = {"ok": 1}
        with patch(
            "shared.shared_infrastructure.src.mongodb.connection.MongoClient",
            return_value=mock_client,
        ):
            m.connect()
        mock_client.admin.command.assert_called_with("ping")


# ─────────────────────────────────────────────────────────────────────────────
# connect — failure & retry
# ─────────────────────────────────────────────────────────────────────────────

class TestConnectRetry:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_raises_connection_failure_after_all_retries_exhausted(self):
        m = _manager(max_retries=3, retry_delay=0.0)
        mock_client = MagicMock()
        mock_client.admin.command.side_effect = ConnectionFailure("timeout")
        with patch(
            "shared.shared_infrastructure.src.mongodb.connection.MongoClient",
            return_value=mock_client,
        ):
            with pytest.raises(ConnectionFailure):
                m.connect()

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_retries_correct_number_of_times(self):
        m = _manager(max_retries=3, retry_delay=0.0)
        mock_client = MagicMock()
        mock_client.admin.command.side_effect = ConnectionFailure("down")
        with patch(
            "shared.shared_infrastructure.src.mongodb.connection.MongoClient",
            return_value=mock_client,
        ):
            with pytest.raises(ConnectionFailure):
                m.connect()
        # ping called once per attempt
        assert mock_client.admin.command.call_count == 3

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_succeeds_on_second_attempt(self):
        m = _manager(max_retries=3, retry_delay=0.0)
        mock_client = MagicMock()
        mock_client.admin.command.side_effect = [
            ConnectionFailure("first attempt fails"),
            {"ok": 1},  # second attempt succeeds
        ]
        with patch(
            "shared.shared_infrastructure.src.mongodb.connection.MongoClient",
            return_value=mock_client,
        ):
            m.connect()
        assert m._client is mock_client

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_handles_server_selection_timeout_as_retriable(self):
        m = _manager(max_retries=2, retry_delay=0.0)
        mock_client = MagicMock()
        mock_client.admin.command.side_effect = ServerSelectionTimeoutError("timeout")
        with patch(
            "shared.shared_infrastructure.src.mongodb.connection.MongoClient",
            return_value=mock_client,
        ):
            with pytest.raises(ConnectionFailure):
                m.connect()
        assert mock_client.admin.command.call_count == 2


# ─────────────────────────────────────────────────────────────────────────────
# disconnect
# ─────────────────────────────────────────────────────────────────────────────

class TestDisconnect:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_disconnect_calls_client_close(self):
        m = _manager()
        mock_client = MagicMock()
        mock_client.admin.command.return_value = {"ok": 1}
        with patch(
            "shared.shared_infrastructure.src.mongodb.connection.MongoClient",
            return_value=mock_client,
        ):
            m.connect()
            m.disconnect()
        mock_client.close.assert_called_once()
        assert m._client is None

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_disconnect_is_safe_when_not_connected(self):
        m = _manager()
        m.disconnect()  # should not raise
        assert m._client is None


# ─────────────────────────────────────────────────────────────────────────────
# reconnect
# ─────────────────────────────────────────────────────────────────────────────

class TestReconnect:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_reconnect_disconnects_then_reconnects(self):
        m = _manager()
        mock_client = MagicMock()
        mock_client.admin.command.return_value = {"ok": 1}
        with patch(
            "shared.shared_infrastructure.src.mongodb.connection.MongoClient",
            return_value=mock_client,
        ) as MockClient:
            m.connect()
            m.reconnect()
        # MongoClient created twice (once per connect call)
        assert MockClient.call_count == 2
        mock_client.close.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_reconnect_increments_reconnect_counter(self):
        m = _manager()
        mock_client = MagicMock()
        mock_client.admin.command.return_value = {"ok": 1}
        with patch(
            "shared.shared_infrastructure.src.mongodb.connection.MongoClient",
            return_value=mock_client,
        ):
            m.connect()
            m.reconnect()
        assert m.metrics.reconnect_attempts >= 1


# ─────────────────────────────────────────────────────────────────────────────
# get_client / get_database
# ─────────────────────────────────────────────────────────────────────────────

class TestAccessors:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_get_client_raises_when_not_connected(self):
        m = _manager()
        with pytest.raises(RuntimeError, match="not connected"):
            m.get_client()

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_get_database_returns_db_handle(self):
        m = _manager()
        mock_client = MagicMock()
        mock_client.admin.command.return_value = {"ok": 1}
        mock_db = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)
        with patch(
            "shared.shared_infrastructure.src.mongodb.connection.MongoClient",
            return_value=mock_client,
        ):
            m.connect()
            db = m.get_database("auth_service")
        assert db is mock_db


# ─────────────────────────────────────────────────────────────────────────────
# ping
# ─────────────────────────────────────────────────────────────────────────────

class TestPing:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_ping_returns_false_when_not_connected(self):
        m = _manager()
        assert m.ping() is False
        assert m.metrics.last_ping_ok is False

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_ping_returns_true_on_success(self):
        m = _manager()
        mock_client = MagicMock()
        mock_client.admin.command.return_value = {"ok": 1}
        with patch(
            "shared.shared_infrastructure.src.mongodb.connection.MongoClient",
            return_value=mock_client,
        ):
            m.connect()
            result = m.ping()
        assert result is True
        assert m.metrics.last_ping_ok is True

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_ping_returns_false_and_never_raises_on_connection_failure(self):
        m = _manager()
        mock_client = MagicMock()
        mock_client.admin.command.side_effect = [
            {"ok": 1},           # connect ping succeeds
            ConnectionFailure("gone"),  # health ping fails
        ]
        with patch(
            "shared.shared_infrastructure.src.mongodb.connection.MongoClient",
            return_value=mock_client,
        ):
            m.connect()
            result = m.ping()
        assert result is False  # no exception raised


# ─────────────────────────────────────────────────────────────────────────────
# health_status
# ─────────────────────────────────────────────────────────────────────────────

class TestHealthStatus:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_unhealthy_when_not_connected(self):
        m = _manager()
        status = m.health_status()
        assert status["mongodb"]["status"] == "unhealthy"
        assert status["mongodb"]["connected"] is False
        assert status["mongodb"]["latency_ms"] is None

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_healthy_on_successful_ping(self):
        m = _manager()
        mock_client = MagicMock()
        mock_client.admin.command.return_value = {"ok": 1}
        mock_client.topology_description.server_descriptions.return_value = {}
        with patch(
            "shared.shared_infrastructure.src.mongodb.connection.MongoClient",
            return_value=mock_client,
        ):
            m.connect()
            status = m.health_status()
        assert status["mongodb"]["status"] == "healthy"
        assert status["mongodb"]["connected"] is True
        assert status["mongodb"]["latency_ms"] is not None

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_health_status_schema_contains_required_keys(self):
        m = _manager()
        status = m.health_status()
        mongo = status["mongodb"]
        for key in ("status", "connected", "latency_ms", "pool", "metrics", "checked_at"):
            assert key in mongo, f"Missing key: {key}"

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_health_status_includes_metrics_snapshot(self):
        m = _manager()
        mock_client = MagicMock()
        mock_client.admin.command.return_value = {"ok": 1}
        mock_client.topology_description.server_descriptions.return_value = {}
        with patch(
            "shared.shared_infrastructure.src.mongodb.connection.MongoClient",
            return_value=mock_client,
        ):
            m.connect()
            m.metrics.record_op(15.0)
            status = m.health_status()
        metrics_snap = status["mongodb"]["metrics"]
        assert metrics_snap["total_operations"] == 1
        assert metrics_snap["avg_latency_ms"] == 15.0

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_health_status_checked_at_is_iso8601(self):
        m = _manager()
        from datetime import datetime, timezone
        status = m.health_status()
        checked_at = status["mongodb"]["checked_at"]
        # Must be parseable as ISO 8601
        parsed = datetime.fromisoformat(checked_at)
        assert parsed.tzinfo is not None
