"""Tests for api-service JWT middleware and HTTP propagation."""

import json

import jwt
import pytest

from services.api_service.src.config import get_config
from services.api_service.src.presentation.app import create_app
from services.auth_service.src.domain.entities.user import User
from services.auth_service.src.infrastructure.security.jwt_service import JwtTokenService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_JWT_SETTINGS = dict(
    secret_key="test-secret-key-at-least-32-chars-long",
    algorithm="HS256",
    issuer="auth_service",
    audience="ai_platform",
    access_token_ttl_seconds=900,
    refresh_token_ttl_seconds=86400,
    allow_dev_secret=True,
)


def _make_token(roles=None) -> str:
    svc = JwtTokenService.from_settings(**_JWT_SETTINGS)
    user = User.create(
        provider="github",
        provider_user_id="1",
        email="api@example.com",
        display_name="API User",
        roles=roles or ["user"],
    )
    access, _ = svc.issue_access_token(user, session_id="sess-1")
    return access


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-at-least-32-chars-long")
    monkeypatch.setenv("JWT_ISSUER", "auth_service")
    monkeypatch.setenv("JWT_AUDIENCE", "ai_platform")
    monkeypatch.setenv("JWT_AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_AUTH_REQUIRED", "false")
    return create_app()


@pytest.fixture
def token():
    return _make_token(roles=["user"])


@pytest.fixture
def admin_token():
    return _make_token(roles=["admin"])


# ---------------------------------------------------------------------------
# Health (public — no token needed)
# ---------------------------------------------------------------------------

def test_health_without_token(app):
    resp = app.test_client().get("/health")
    assert resp.status_code == 200


def test_correlation_id_in_response(app, token):
    resp = app.test_client().get(
        "/health",
        headers={"X-Correlation-ID": "corr-abc"},
    )
    assert resp.headers.get("X-Correlation-ID") == "corr-abc"


# ---------------------------------------------------------------------------
# Job routes — authentication required unconditionally
# ---------------------------------------------------------------------------

def test_jobs_requires_auth_without_token(app):
    """Every job route must reject unauthenticated requests with 401."""
    client = app.test_client()
    assert client.get("/api/v1/jobs").status_code == 401


def test_jobs_accepts_valid_jwt(app, token):
    resp = app.test_client().get(
        "/api/v1/jobs",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Correlation-ID": "corr-jwt-test",
        },
    )
    # Repository is stubbed — expect not 401/403
    assert resp.status_code not in (401, 403)


def test_invalid_jwt_returns_401(app):
    resp = app.test_client().get(
        "/api/v1/jobs",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# JWT_AUTH_REQUIRED=true still works (global middleware enforcement)
# ---------------------------------------------------------------------------

def test_jwt_auth_required_blocks_jobs(monkeypatch):
    monkeypatch.setenv("JWT_AUTH_REQUIRED", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-at-least-32-chars-long")
    monkeypatch.setenv("JWT_ISSUER", "auth_service")
    monkeypatch.setenv("JWT_AUDIENCE", "ai_platform")
    app = create_app(get_config("testing"))
    client = app.test_client()

    # Without token: rejected by global middleware (before @require_auth fires)
    denied = client.get("/api/v1/jobs")
    assert denied.status_code == 401

    token = _make_token()
    allowed = client.get(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert allowed.status_code not in (401, 403)


# ---------------------------------------------------------------------------
# Propagation context
# ---------------------------------------------------------------------------

def test_build_outbound_headers_includes_correlation():
    from shared.shared_http import build_outbound_headers, set_request_context

    set_request_context(correlation_id="corr-out", bearer_token="tok-123")
    headers = build_outbound_headers()
    assert headers["X-Correlation-ID"] == "corr-out"
    assert headers["Authorization"] == "Bearer tok-123"
