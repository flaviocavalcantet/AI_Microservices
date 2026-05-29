"""tests/mongodb/endpoint/conftest.py

Endpoint-layer fixtures: Flask test apps with mongo_manager injected.

Three variants are provided:
  - healthy_client   → mongo_manager returns status=healthy
  - unhealthy_client → mongo_manager returns status=unhealthy
  - unconfigured_client → no mongo_manager registered (in-memory mode)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services.auth_service.src.container import ServiceContainer, get_container
from services.auth_service.src.presentation.app import create_app


# ─────────────────────────────────────────────────────────────────────────────
# Mock manager builders
# ─────────────────────────────────────────────────────────────────────────────

def _make_manager(status: str = "healthy", latency: float = 1.5) -> MagicMock:
    from shared.shared_infrastructure.src.mongodb.connection import MongoConnectionManager
    mgr = MagicMock(spec=MongoConnectionManager)
    mgr.health_status.return_value = {
        "mongodb": {
            "status": status,
            "connected": status == "healthy",
            "latency_ms": latency if status == "healthy" else None,
            "pool": {"server_type": "Standalone", "round_trip_time_ms": latency},
            "metrics": {
                "connect_attempts": 1,
                "connect_successes": 1 if status == "healthy" else 0,
                "connect_failures": 0 if status == "healthy" else 1,
                "reconnect_attempts": 0,
                "total_operations": 42,
                "failed_operations": 0,
                "avg_latency_ms": latency,
                "connected_at": "2026-01-15T10:00:00+00:00",
                "last_ping_at": "2026-01-15T10:05:00+00:00",
                "last_ping_ok": status == "healthy",
            },
            "checked_at": "2026-01-15T10:05:00+00:00",
        }
    }
    return mgr


# ─────────────────────────────────────────────────────────────────────────────
# App factory with injected manager
# ─────────────────────────────────────────────────────────────────────────────

def _make_app(monkeypatch, manager=None):
    monkeypatch.setenv("FLASK_ENV", "testing")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "ci-id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "ci-secret")
    # Ensure MONGODB_URI is absent so app factory skips real MongoDB wiring
    monkeypatch.delenv("MONGODB_URI", raising=False)

    app = create_app()

    if manager is not None:
        # Register the mock manager into the container that was initialised
        # during create_app() so health/metrics routes can resolve it.
        container = get_container()
        container.register_instance("mongo_manager", manager)

    return app


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def healthy_client(monkeypatch):
    """Flask test client with a healthy mongo_manager registered."""
    mgr = _make_manager(status="healthy")
    app = _make_app(monkeypatch, manager=mgr)
    yield app.test_client()


@pytest.fixture
def unhealthy_client(monkeypatch):
    """Flask test client with an unhealthy mongo_manager registered."""
    mgr = _make_manager(status="unhealthy", latency=None)
    app = _make_app(monkeypatch, manager=mgr)
    yield app.test_client()


@pytest.fixture
def unconfigured_client(monkeypatch):
    """Flask test client with NO mongo_manager (pure in-memory mode)."""
    app = _make_app(monkeypatch, manager=None)
    yield app.test_client()
