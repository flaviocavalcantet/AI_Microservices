"""Tests for job-route auth enforcement and role-based access control.

Covers:
- Every job endpoint rejects requests without a token (401).
- Every job endpoint rejects a valid token for the wrong user (403).
- Admin tokens bypass ownership checks.
- Non-admin users cannot list another user's jobs via ?user_id=.
- cancel and delete propagate ownership into the use case.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from services.api_service.src.presentation.app import create_app
from services.auth_service.src.domain.entities.user import User
from services.auth_service.src.infrastructure.security.jwt_service import JwtTokenService

# ---------------------------------------------------------------------------
# Token factory
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

_USER_ID_A = "user-aaa"
_USER_ID_B = "user-bbb"
_ADMIN_ID  = "user-admin"


def _token(user_id: str, roles: list[str]) -> str:
    svc = JwtTokenService.from_settings(**_JWT_SETTINGS)
    user = User(
        id=user_id,
        provider="github",
        provider_user_id=user_id,
        email=f"{user_id}@example.com",
        display_name=user_id,
        roles=roles,
        is_active=True,
        created_at=__import__("datetime").datetime.utcnow(),
    )
    access, _ = svc.issue_access_token(user, session_id="sess-test")
    return access


def _user_token(user_id: str = _USER_ID_A) -> str:
    return _token(user_id, ["user"])


def _admin_token() -> str:
    return _token(_ADMIN_ID, ["admin"])


# ---------------------------------------------------------------------------
# App fixture
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
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALL_JOB_ROUTES = [
    ("GET",    "/api/v1/jobs"),
    ("POST",   "/api/v1/jobs"),
    ("GET",    "/api/v1/jobs/job-x"),
    ("PUT",    "/api/v1/jobs/job-x"),
    ("DELETE", "/api/v1/jobs/job-x"),
    ("POST",   "/api/v1/jobs/job-x/cancel"),
]

_CONTENT = {"Content-Type": "application/json"}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", **_CONTENT}


# ---------------------------------------------------------------------------
# 1. Every job route requires authentication
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method,path", _ALL_JOB_ROUTES)
def test_all_job_routes_require_auth(client, method, path):
    """No job endpoint is reachable without a valid JWT."""
    resp = client.open(path, method=method)
    assert resp.status_code == 401, (
        f"{method} {path} returned {resp.status_code}, expected 401"
    )


# ---------------------------------------------------------------------------
# 2. Authenticated user can reach routes (repo errors expected, not 401/403)
# ---------------------------------------------------------------------------

def test_authenticated_user_can_list_own_jobs(client):
    token = _user_token(_USER_ID_A)
    resp = client.get("/api/v1/jobs", headers=_auth(token))
    assert resp.status_code not in (401, 403)


def test_authenticated_user_can_create_job(client):
    token = _user_token(_USER_ID_A)
    resp = client.post(
        "/api/v1/jobs",
        data=json.dumps({"job_type": "training", "input_data": {}}),
        headers=_auth(token),
    )
    assert resp.status_code not in (401, 403)


# ---------------------------------------------------------------------------
# 3. Non-admin cannot list another user's jobs via ?user_id=
# ---------------------------------------------------------------------------

def test_non_admin_cannot_list_other_users_jobs(client):
    token = _user_token(_USER_ID_A)
    resp = client.get(
        f"/api/v1/jobs?user_id={_USER_ID_B}",
        headers=_auth(token),
    )
    assert resp.status_code == 403


def test_admin_can_list_any_users_jobs(client):
    token = _admin_token()
    resp = client.get(
        f"/api/v1/jobs?user_id={_USER_ID_B}",
        headers=_auth(token),
    )
    # May 404/500 due to stubbed repo — but not 403
    assert resp.status_code not in (401, 403)


# ---------------------------------------------------------------------------
# 4. Ownership checks on GET, PUT, DELETE, cancel
# ---------------------------------------------------------------------------

def _make_job_dto(owner_id: str):
    """Return a minimal fake JobDTO dict owned by owner_id."""
    from services.api_service.src.application.dto.job_dto import JobDTO
    return JobDTO(
        id="job-x",
        user_id=owner_id,
        job_type="training",
        status="pending",
        priority=5,
        created_at="2026-01-01T00:00:00Z",
        input_data={},
        timeout_seconds=3600,
    )


def _patch_get_uc(owner_id: str):
    """Context manager that makes get_job_use_case return a job owned by owner_id."""
    mock_uc = MagicMock()
    mock_uc.execute.return_value = _make_job_dto(owner_id)
    return patch(
        "services.api_service.src.presentation.routes.v1.jobs.controller.resolve_from_context",
        side_effect=lambda name: mock_uc if "get_job" in name else MagicMock(),
    )


def test_get_job_owned_by_caller_succeeds(client):
    token = _user_token(_USER_ID_A)
    with _patch_get_uc(_USER_ID_A):
        resp = client.get("/api/v1/jobs/job-x", headers=_auth(token))
    assert resp.status_code not in (401, 403)


def test_get_job_owned_by_other_user_returns_403(client):
    token = _user_token(_USER_ID_A)
    with _patch_get_uc(_USER_ID_B):
        resp = client.get("/api/v1/jobs/job-x", headers=_auth(token))
    assert resp.status_code == 403


def test_admin_can_get_any_job(client):
    token = _admin_token()
    with _patch_get_uc(_USER_ID_B):
        resp = client.get("/api/v1/jobs/job-x", headers=_auth(token))
    assert resp.status_code not in (401, 403)


def test_put_job_owned_by_other_user_returns_403(client):
    token = _user_token(_USER_ID_A)
    with _patch_get_uc(_USER_ID_B):
        resp = client.put(
            "/api/v1/jobs/job-x",
            data=json.dumps({"priority": 3}),
            headers=_auth(token),
        )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 5. Delete: PermissionError from use case surfaces as 403
# ---------------------------------------------------------------------------

def test_delete_other_users_job_returns_403(client):
    token = _user_token(_USER_ID_A)
    mock_uc = MagicMock()
    mock_uc.execute.side_effect = PermissionError("You can only delete your own jobs.")
    with patch(
        "services.api_service.src.presentation.routes.v1.jobs.controller.resolve_from_context",
        return_value=mock_uc,
    ):
        resp = client.delete("/api/v1/jobs/job-x", headers=_auth(token))
    assert resp.status_code == 403


def test_admin_delete_calls_use_case_with_is_admin_true(client):
    token = _admin_token()
    mock_uc = MagicMock()
    mock_uc.execute.return_value = True
    with patch(
        "services.api_service.src.presentation.routes.v1.jobs.controller.resolve_from_context",
        return_value=mock_uc,
    ):
        client.delete("/api/v1/jobs/job-x", headers=_auth(token))
    _, kwargs = mock_uc.execute.call_args
    assert kwargs.get("is_admin") is True


# ---------------------------------------------------------------------------
# 6. Cancel: PermissionError from use case surfaces as 403
# ---------------------------------------------------------------------------

def test_cancel_other_users_job_returns_403(client):
    token = _user_token(_USER_ID_A)
    mock_uc = MagicMock()
    mock_uc.execute.side_effect = PermissionError("You can only cancel your own jobs.")
    with patch(
        "services.api_service.src.presentation.routes.v1.jobs.controller.resolve_from_context",
        return_value=mock_uc,
    ):
        resp = client.post("/api/v1/jobs/job-x/cancel", headers=_auth(token))
    assert resp.status_code == 403


def test_cancel_calls_use_case_with_caller_user_id(client):
    token = _user_token(_USER_ID_A)
    mock_uc = MagicMock()
    mock_uc.execute.return_value = _make_job_dto(_USER_ID_A)
    with patch(
        "services.api_service.src.presentation.routes.v1.jobs.controller.resolve_from_context",
        return_value=mock_uc,
    ):
        client.post("/api/v1/jobs/job-x/cancel", headers=_auth(token))
    _, kwargs = mock_uc.execute.call_args
    assert kwargs.get("user_id") == _USER_ID_A
    assert kwargs.get("is_admin") is False
