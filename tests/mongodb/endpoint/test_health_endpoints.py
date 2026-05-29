"""tests/mongodb/endpoint/test_health_endpoints.py

Layer 5 — /health endpoint tests with MongoDB status integration.

Tests the three health routes:
  - GET /health          → liveness (always 200)
  - GET /health/ready    → readiness (200 healthy, 503 degraded)
  - GET /health/live     → liveness alias
"""

from __future__ import annotations

import json

import pytest


pytestmark = [pytest.mark.e2e, pytest.mark.mongodb]

CORRELATION_HEADERS = {
    "X-Correlation-ID": "test-corr-health",
    "X-Request-ID": "test-req-health",
}


# ─────────────────────────────────────────────────────────────────────────────
# GET /health  (liveness — always 200)
# ─────────────────────────────────────────────────────────────────────────────

class TestHealthLiveness:
    def test_returns_200(self, healthy_client):
        resp = healthy_client.get("/health")
        assert resp.status_code == 200

    def test_returns_healthy_status(self, healthy_client):
        resp = healthy_client.get("/health")
        body = json.loads(resp.data)
        assert body["status"] == "healthy"

    def test_contains_service_name(self, healthy_client):
        resp = healthy_client.get("/health")
        body = json.loads(resp.data)
        assert "service" in body

    def test_contains_iso_timestamp(self, healthy_client):
        from datetime import datetime
        resp = healthy_client.get("/health")
        body = json.loads(resp.data)
        assert "timestamp" in body
        datetime.fromisoformat(body["timestamp"])  # must be parseable

    def test_liveness_returns_200_even_with_unhealthy_mongo(self, unhealthy_client):
        """Liveness probe must never fail due to external dependencies."""
        resp = unhealthy_client.get("/health")
        assert resp.status_code == 200

    def test_liveness_returns_200_with_no_mongo_configured(self, unconfigured_client):
        resp = unconfigured_client.get("/health")
        assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# GET /health/live
# ─────────────────────────────────────────────────────────────────────────────

class TestHealthLive:
    def test_returns_200(self, healthy_client):
        resp = healthy_client.get("/health/live")
        assert resp.status_code == 200

    def test_returns_alive_status(self, healthy_client):
        body = json.loads(healthy_client.get("/health/live").data)
        assert body["status"] == "alive"


# ─────────────────────────────────────────────────────────────────────────────
# GET /health/ready — healthy MongoDB
# ─────────────────────────────────────────────────────────────────────────────

class TestReadinessHealthy:
    def test_returns_200_when_mongo_healthy(self, healthy_client):
        resp = healthy_client.get("/health/ready")
        assert resp.status_code == 200

    def test_status_is_ready(self, healthy_client):
        body = json.loads(healthy_client.get("/health/ready").data)
        assert body["status"] == "ready"

    def test_response_contains_dependencies(self, healthy_client):
        body = json.loads(healthy_client.get("/health/ready").data)
        assert "dependencies" in body

    def test_database_dependency_is_healthy(self, healthy_client):
        body = json.loads(healthy_client.get("/health/ready").data)
        db_info = body["dependencies"]["database"]
        assert db_info["status"] == "healthy"

    def test_database_connected_is_true(self, healthy_client):
        body = json.loads(healthy_client.get("/health/ready").data)
        assert body["dependencies"]["database"]["connected"] is True

    def test_database_latency_ms_is_present(self, healthy_client):
        body = json.loads(healthy_client.get("/health/ready").data)
        assert body["dependencies"]["database"]["latency_ms"] is not None

    def test_response_is_json(self, healthy_client):
        resp = healthy_client.get("/health/ready")
        assert resp.content_type == "application/json"

    def test_v1_route_alias_works(self, healthy_client):
        resp = healthy_client.get("/api/v1/auth/health/ready")
        assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# GET /health/ready — unhealthy MongoDB → 503
# ─────────────────────────────────────────────────────────────────────────────

class TestReadinessUnhealthy:
    def test_returns_503_when_mongo_unhealthy(self, unhealthy_client):
        resp = unhealthy_client.get("/health/ready")
        assert resp.status_code == 503

    def test_status_is_degraded(self, unhealthy_client):
        body = json.loads(unhealthy_client.get("/health/ready").data)
        assert body["status"] == "degraded"

    def test_database_status_is_unhealthy(self, unhealthy_client):
        body = json.loads(unhealthy_client.get("/health/ready").data)
        assert body["dependencies"]["database"]["status"] == "unhealthy"

    def test_database_connected_is_false(self, unhealthy_client):
        body = json.loads(unhealthy_client.get("/health/ready").data)
        assert body["dependencies"]["database"]["connected"] is False


# ─────────────────────────────────────────────────────────────────────────────
# GET /health/ready — no MongoDB configured (in-memory mode)
# ─────────────────────────────────────────────────────────────────────────────

class TestReadinessUnconfigured:
    def test_returns_200_in_memory_mode(self, unconfigured_client):
        """When no mongo_manager is registered the app runs in-memory mode
        and readiness should still pass (not_configured is treated as OK)."""
        resp = unconfigured_client.get("/health/ready")
        assert resp.status_code == 200

    def test_database_status_is_not_configured(self, unconfigured_client):
        body = json.loads(unconfigured_client.get("/health/ready").data)
        db_info = body["dependencies"]["database"]
        assert db_info["status"] == "not_configured"

    def test_message_queue_is_not_configured(self, unconfigured_client):
        body = json.loads(unconfigured_client.get("/health/ready").data)
        assert body["dependencies"]["message_queue"] == "not_configured"


# ─────────────────────────────────────────────────────────────────────────────
# Response schema validation (present on all /health/ready responses)
# ─────────────────────────────────────────────────────────────────────────────

class TestReadinessResponseSchema:
    @pytest.mark.parametrize("client_fixture", ["healthy_client", "unconfigured_client"])
    def test_required_top_level_keys_present(self, request, client_fixture):
        client = request.getfixturevalue(client_fixture)
        body = json.loads(client.get("/health/ready").data)
        for key in ("status", "service", "timestamp", "dependencies"):
            assert key in body, f"Missing key: {key}"

    def test_timestamp_is_iso8601(self, healthy_client):
        from datetime import datetime
        body = json.loads(healthy_client.get("/health/ready").data)
        datetime.fromisoformat(body["timestamp"])
