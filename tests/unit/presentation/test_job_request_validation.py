"""Tests for Jobs API request validation.

These tests focus on schema validation, not auth logic.  The fixture disables
JWT validation (JWT_AUTH_ENABLED=false) so tests can reach the validation layer
without having to supply a real token on every call.  Auth behaviour is covered
separately in test_jwt_propagation.py.
"""

import pytest

from services.api_service.src.presentation.app import create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")
    # Disable JWT enforcement so validation tests are not coupled to auth.
    monkeypatch.setenv("JWT_AUTH_ENABLED", "false")
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_create_job_rejects_non_json_body(client):
    response = client.post("/api/v1/jobs", data="not-json")

    assert response.status_code == 400
    assert response.get_json()["error"] == "Content-Type must be application/json"


def test_create_job_rejects_missing_required_field(client):
    response = client.post(
        "/api/v1/jobs",
        json={"job_type": "training"},
        headers={"X-User-ID": "user-123"},
    )

    payload = response.get_json()
    assert response.status_code == 400
    assert payload["error"] == "Invalid request body"
    assert payload["details"]["validation_errors"][0]["field"] == "input_data"


def test_create_job_uses_anonymous_user_when_no_token(client):
    """Without a JWT the caller identity falls back to 'anonymous'."""
    response = client.post(
        "/api/v1/jobs",
        json={"job_type": "training", "input_data": {}, "priority": 5},
    )

    payload = response.get_json()
    assert response.status_code == 201
    assert payload["data"]["user_id"] == "anonymous"


def test_list_jobs_rejects_invalid_query_params(client):
    response = client.get("/api/v1/jobs?limit=0&status=bogus&sort_by=name")

    payload = response.get_json()
    fields = {error["field"] for error in payload["details"]["validation_errors"]}
    assert response.status_code == 400
    assert payload["error"] == "Invalid query parameters"
    assert {"limit", "status", "sort_by"}.issubset(fields)


def test_update_job_rejects_empty_body_before_repository_lookup(client):
    response = client.put("/api/v1/jobs/job-123", json={})

    payload = response.get_json()
    assert response.status_code == 400
    assert payload["error"] == "Invalid request body"
    assert payload["details"]["validation_errors"][0]["field"] == "__root__"
