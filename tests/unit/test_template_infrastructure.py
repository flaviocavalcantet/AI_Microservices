"""Tests for application-template infrastructure behavior."""

import json
import logging

from services.api_service.src.container import ServiceContainer
from services.api_service.src.config import get_config
from services.api_service.src.logger import JSONFormatter
from services.api_service.src.presentation.app import create_app


def test_container_singleton_registration_reuses_instance():
    container = ServiceContainer()
    calls = 0

    def factory():
        nonlocal calls
        calls += 1
        return object()

    container.register("service", factory, singleton=True)

    first = container.resolve("service")
    second = container.resolve("service")

    assert first is second
    assert calls == 1


def test_container_transient_registration_creates_new_instances():
    container = ServiceContainer()
    container.register("service", object, singleton=False)

    assert container.resolve("service") is not container.resolve("service")


def test_request_context_preserves_incoming_correlation_headers(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")
    app = create_app()
    app.config.update(TESTING=True)

    response = app.test_client().get(
        "/health",
        headers={
            "X-Correlation-ID": "corr-123",
            "X-Request-ID": "req-456",
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "corr-123"
    assert response.headers["X-Request-ID"] == "req-456"


def test_environment_config_profiles_apply_expected_overrides():
    development = get_config("development")
    testing = get_config("testing")
    staging = get_config("staging")

    assert development.FLASK_ENV == "development"
    assert development.DEBUG is True
    assert development.LOG_LEVEL == "DEBUG"
    assert development.CORS_ALLOWED_ORIGINS == ["*"]
    assert testing.TESTING is True
    assert staging.CORS_ALLOWED_ORIGINS == ["https://staging.example.com"]


def test_json_formatter_includes_custom_extra_fields():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.environment = "testing"
    record.service = "api_service"

    payload = json.loads(JSONFormatter().format(record))

    assert payload["environment"] == "testing"
    assert payload["service"] == "api_service"
