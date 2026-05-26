"""Tests for auth-service template infrastructure."""

import json
import logging

import pytest

from services.auth_service.src.application.ports.interfaces import IAuthorizationPolicy, ITokenService
from services.auth_service.src.config import get_config
from services.auth_service.src.container import ServiceContainer, get_container
from services.auth_service.src.infrastructure.security.jwt_service import JwtTokenService
from services.auth_service.src.infrastructure.security.oauth_registry import OAuthProviderRegistry
from services.auth_service.src.logger import JSONFormatter
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

    assert isinstance(container.resolve("token_service"), ITokenService)
    assert isinstance(container.resolve("token_service"), JwtTokenService)
    assert isinstance(container.resolve("oauth_provider_registry"), OAuthProviderRegistry)
    assert isinstance(container.resolve("authorization_policy"), IAuthorizationPolicy)


def test_jwt_service_issues_and_validates_tokens(app):
    from services.auth_service.src.domain.entities.user import User

    token_service = get_container().resolve("token_service")
    user = User.create(
        provider="github",
        provider_user_id="1",
        email="test@example.com",
        display_name="Test",
    )
    token, jti = token_service.issue_access_token(user)
    claims = token_service.validate_access_token(token)
    assert claims.user_id == user.id
    assert claims.token_type == "access"
    assert jti

    pair = token_service.issue_token_pair(user, session_id="test-session")
    assert token_service.validate_refresh_token(pair.refresh_token).session_id == "test-session"


def test_auth_routes_are_registered(app):
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/v1/auth/login" in rules
    assert "/api/v1/auth/refresh" in rules
    assert "/api/v1/auth/oauth/github" in rules
    assert "/api/v1/auth/oauth/github/callback" in rules


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
