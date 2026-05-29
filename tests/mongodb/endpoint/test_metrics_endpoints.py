"""tests/mongodb/endpoint/test_metrics_endpoints.py

Layer 5 — GET /api/v1/auth/metrics/mongodb endpoint tests.

Validates the full response schema, HTTP status codes, and graceful
degradation when MongoDB is unhealthy or not configured.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest


pytestmark = [pytest.mark.e2e, pytest.mark.mongodb]


# ─────────────────────────────────────────────────────────────────────────────
# Route registration
# ─────────────────────────────────────────────────────────────────────────────

class TestRouteRegistered:
    def test_metrics_route_exists(self, healthy_client):
        resp = healthy_client.get("/api/v1/auth/metrics/mongodb")
        assert resp.status_code != 404

    def test_response_is_json(self, healthy_client):
        resp = healthy_client.get("/api/v1/auth/metrics/mongodb")
        assert "application/json" in resp.content_type


# ─────────────────────────────────────────────────────────────────────────────
# Healthy MongoDB
# ─────────────────────────────────────────────────────────────────────────────

class TestMetricsHealthy:
    def test_returns_200_when_healthy(self, healthy_client):
        resp = healthy_client.get("/api/v1/auth/metrics/mongodb")
        assert resp.status_code == 200

    def test_mongodb_status_is_healthy(self, healthy_client):
        body = json.loads(healthy_client.get("/api/v1/auth/metrics/mongodb").data)
        assert body["mongodb"]["status"] == "healthy"

    def test_mongodb_connected_is_true(self, healthy_client):
        body = json.loads(healthy_client.get("/api/v1/auth/metrics/mongodb").data)
        assert body["mongodb"]["connected"] is True

    def test_latency_ms_is_present(self, healthy_client):
        body = json.loads(healthy_client.get("/api/v1/auth/metrics/mongodb").data)
        assert body["mongodb"]["latency_ms"] is not None

    def test_metrics_nested_object_present(self, healthy_client):
        body = json.loads(healthy_client.get("/api/v1/auth/metrics/mongodb").data)
        assert "metrics" in body["mongodb"]

    def test_metrics_contains_operation_counters(self, healthy_client):
        body = json.loads(healthy_client.get("/api/v1/auth/metrics/mongodb").data)
        metrics = body["mongodb"]["metrics"]
        for key in ("total_operations", "failed_operations", "avg_latency_ms"):
            assert key in metrics, f"Missing metrics key: {key}"

    def test_metrics_contains_connection_counters(self, healthy_client):
        body = json.loads(healthy_client.get("/api/v1/auth/metrics/mongodb").data)
        metrics = body["mongodb"]["metrics"]
        for key in ("connect_attempts", "connect_successes", "connect_failures",
                    "reconnect_attempts"):
            assert key in metrics, f"Missing metrics key: {key}"

    def test_metrics_contains_timestamps(self, healthy_client):
        body = json.loads(healthy_client.get("/api/v1/auth/metrics/mongodb").data)
        metrics = body["mongodb"]["metrics"]
        for key in ("connected_at", "last_ping_at", "last_ping_ok"):
            assert key in metrics, f"Missing metrics key: {key}"

    def test_checked_at_is_iso8601(self, healthy_client):
        body = json.loads(healthy_client.get("/api/v1/auth/metrics/mongodb").data)
        checked_at = body["mongodb"]["checked_at"]
        datetime.fromisoformat(checked_at)  # raises if not valid ISO 8601

    def test_pool_info_present(self, healthy_client):
        body = json.loads(healthy_client.get("/api/v1/auth/metrics/mongodb").data)
        assert "pool" in body["mongodb"]

    def test_top_level_service_field_present(self, healthy_client):
        body = json.loads(healthy_client.get("/api/v1/auth/metrics/mongodb").data)
        assert "service" in body
        assert body["service"] == "auth_service"

    def test_top_level_timestamp_present(self, healthy_client):
        body = json.loads(healthy_client.get("/api/v1/auth/metrics/mongodb").data)
        assert "timestamp" in body
        datetime.fromisoformat(body["timestamp"])


# ─────────────────────────────────────────────────────────────────────────────
# Unhealthy MongoDB → 503
# ─────────────────────────────────────────────────────────────────────────────

class TestMetricsUnhealthy:
    def test_returns_503_when_unhealthy(self, unhealthy_client):
        resp = unhealthy_client.get("/api/v1/auth/metrics/mongodb")
        assert resp.status_code == 503

    def test_mongodb_status_is_unhealthy(self, unhealthy_client):
        body = json.loads(unhealthy_client.get("/api/v1/auth/metrics/mongodb").data)
        assert body["mongodb"]["status"] == "unhealthy"

    def test_mongodb_connected_is_false(self, unhealthy_client):
        body = json.loads(unhealthy_client.get("/api/v1/auth/metrics/mongodb").data)
        assert body["mongodb"]["connected"] is False

    def test_latency_ms_is_none_when_unhealthy(self, unhealthy_client):
        body = json.loads(unhealthy_client.get("/api/v1/auth/metrics/mongodb").data)
        assert body["mongodb"]["latency_ms"] is None


# ─────────────────────────────────────────────────────────────────────────────
# No MongoDB configured (in-memory mode) → 200
# ─────────────────────────────────────────────────────────────────────────────

class TestMetricsUnconfigured:
    def test_returns_200_when_not_configured(self, unconfigured_client):
        resp = unconfigured_client.get("/api/v1/auth/metrics/mongodb")
        assert resp.status_code == 200

    def test_mongodb_status_is_not_configured(self, unconfigured_client):
        body = json.loads(unconfigured_client.get("/api/v1/auth/metrics/mongodb").data)
        assert body["mongodb"]["status"] == "not_configured"

    def test_connected_is_false_when_not_configured(self, unconfigured_client):
        body = json.loads(unconfigured_client.get("/api/v1/auth/metrics/mongodb").data)
        assert body["mongodb"]["connected"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Full response schema contract
# ─────────────────────────────────────────────────────────────────────────────

class TestMetricsResponseSchema:
    _REQUIRED_TOP_LEVEL = {"service", "timestamp", "mongodb"}
    _REQUIRED_MONGODB = {"status", "connected", "latency_ms", "pool",
                         "metrics", "checked_at"}

    def test_all_top_level_keys_present(self, healthy_client):
        body = json.loads(healthy_client.get("/api/v1/auth/metrics/mongodb").data)
        missing = self._REQUIRED_TOP_LEVEL - set(body.keys())
        assert not missing, f"Missing top-level keys: {missing}"

    def test_all_mongodb_keys_present(self, healthy_client):
        body = json.loads(healthy_client.get("/api/v1/auth/metrics/mongodb").data)
        missing = self._REQUIRED_MONGODB - set(body["mongodb"].keys())
        assert not missing, f"Missing mongodb keys: {missing}"

    @pytest.mark.parametrize("client_fixture", [
        "healthy_client", "unhealthy_client", "unconfigured_client"
    ])
    def test_service_field_always_present(self, request, client_fixture):
        client = request.getfixturevalue(client_fixture)
        body = json.loads(client.get("/api/v1/auth/metrics/mongodb").data)
        assert "service" in body

    @pytest.mark.parametrize("client_fixture", [
        "healthy_client", "unhealthy_client", "unconfigured_client"
    ])
    def test_mongodb_field_always_present(self, request, client_fixture):
        client = request.getfixturevalue(client_fixture)
        body = json.loads(client.get("/api/v1/auth/metrics/mongodb").data)
        assert "mongodb" in body
