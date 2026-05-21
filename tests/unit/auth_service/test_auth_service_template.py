"""Tests for auth-service template infrastructure."""

import json
import logging

import pytest

from services.auth_service.src.application.ports.authorization_policy import AuthorizationPolicy
from services.auth_service.src.application.ports.oauth_provider import OAuthProvider
from services.auth_service.src.application.ports.token_service import TokenService
from services.auth_service.src.config import get_config
from services.auth_service.src.container import ServiceContainer, get_container
from services.auth_service.src.infrastructure.security.jwt_service import JwtTokenService
from services.auth_service.src.infrastructure.security.oauth_registry import OAuthProviderRegistry
from services.auth_service.src.logger import JSONFormatter
from services.auth_service.src.presentation.app import create_app


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")
    return create_app()


def test_auth_service_health_checks_are_available(app):
    client = app.test_client()

    assert client.get("/health").status_code == 200
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200
    assert client.get("/api/v1/auth/health").status_code == 200


def test_auth_service_preserves_request_correlation_headers(app):
    response = app.test_client().get(
        "/health",
        headers={
            "X-Correlation-ID": "corr-auth",
            "X-Request-ID": "req-auth",
        },
    )

    assert response.headers["X-Correlation-ID"] == "corr-auth"
    assert response.headers["X-Request-ID"] == "req-auth"


def test_auth_infrastructure_ports_are_registered(app):
    container = get_container()

    assert isinstance(container.resolve("token_service"), TokenService)
    assert isinstance(container.resolve("token_service"), JwtTokenService)
    assert isinstance(container.resolve("oauth_provider_registry"), OAuthProviderRegistry)
    assert isinstance(container.resolve("authorization_policy"), AuthorizationPolicy)


def test_jwt_service_is_ready_but_not_implemented(app):
    token_service = get_container().resolve("token_service")

    with pytest.raises(NotImplementedError):
        token_service.issue_access_token("user-123")

    with pytest.raises(NotImplementedError):
        token_service.validate_access_token("token")


def test_environment_config_profiles_apply_expected_overrides():
    development = get_config("development")
    testing = get_config("testing")

    assert development.DEBUG is True
    assert development.LOG_LEVEL == "DEBUG"
    assert development.CORS_ALLOWED_ORIGINS == ["*"]
    assert testing.TESTING is True
    assert testing.FLASK_ENV == "testing"


def test_container_singleton_registration_reuses_instance():
    container = ServiceContainer()
    calls = 0

    def factory():
        nonlocal calls
        calls += 1
        return object()

    container.register("service", factory, singleton=True)

    assert container.resolve("service") is container.resolve("service")
    assert calls == 1


def test_logger_includes_custom_extra_fields():
    record = logging.LogRecord(
        name="auth-test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.service = "auth_service"
    record.environment = "testing"

    payload = json.loads(JSONFormatter().format(record))

    assert payload["service"] == "auth_service"
    assert payload["environment"] == "testing"
