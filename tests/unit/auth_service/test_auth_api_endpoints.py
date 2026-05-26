"""Integration tests for authentication API endpoints."""

import json

import pytest


CORRELATION_HEADERS = {
    "X-Correlation-ID": "corr-api-test",
    "X-Request-ID": "req-api-test",
}


def _start_github_oauth(client):
    """Begin OAuth and return parsed start payload."""
    resp = client.get(
        "/api/v1/auth/oauth/github",
        query_string={"format": "json"},
        headers=CORRELATION_HEADERS,
    )
    assert resp.status_code == 200
    return json.loads(resp.data)["data"]


def test_post_login_starts_oauth(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"provider": "github"},
        headers={**CORRELATION_HEADERS, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert body["status"] == "success"
    assert body["correlation_id"] == "corr-api-test"
    assert "authorization_url" in body["data"]
    assert "code_verifier" in body["data"]


def test_post_login_completes_oauth(client):
    start = _start_github_oauth(client)
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "provider": "github",
            "code": "auth-code",
            "state": start["state"],
            "code_verifier": start["code_verifier"],
        },
        headers={**CORRELATION_HEADERS, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)["data"]
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["expires_in"] > 0


def test_get_github_oauth_redirect(client):
    resp = client.get("/api/v1/auth/oauth/github", headers=CORRELATION_HEADERS)
    assert resp.status_code == 302
    assert "github.example" in resp.headers["Location"]


def test_get_github_callback_issues_tokens(client):
    start = _start_github_oauth(client)
    resp = client.get(
        "/api/v1/auth/oauth/github/callback",
        query_string={"code": "cb-code", "state": start["state"]},
        headers=CORRELATION_HEADERS,
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)["data"]
    assert data["access_token"]
    assert data["refresh_token"]


def test_post_refresh_rotates_tokens(client):
    start = _start_github_oauth(client)
    login = client.post(
        "/api/v1/auth/login",
        json={
            "provider": "github",
            "code": "c",
            "state": start["state"],
            "code_verifier": start["code_verifier"],
        },
        headers={"Content-Type": "application/json"},
    )
    tokens = json.loads(login.data)["data"]

    refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
        headers={**CORRELATION_HEADERS, "Content-Type": "application/json"},
    )
    assert refresh.status_code == 200
    new_tokens = json.loads(refresh.data)["data"]
    assert new_tokens["access_token"]
    assert new_tokens["refresh_token"] != tokens["refresh_token"]


def test_validation_error_standard_format(client):
    resp = client.post(
        "/api/v1/auth/refresh",
        json={},
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    body = json.loads(resp.data)
    assert body["status"] == "error"
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "validation_errors" in body["error"]["details"]


def test_oauth_state_mismatch_returns_structured_error(client):
    resp = client.get(
        "/api/v1/auth/oauth/github/callback",
        query_string={"code": "x", "state": "invalid-state"},
        headers=CORRELATION_HEADERS,
    )
    assert resp.status_code == 400
    body = json.loads(resp.data)
    assert body["error"]["code"] == "OAUTH_STATE_INVALID"


def test_required_endpoints_registered(app):
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/v1/auth/login" in rules
    assert "/api/v1/auth/refresh" in rules
    assert "/api/v1/auth/oauth/github" in rules
    assert "/api/v1/auth/oauth/github/callback" in rules
