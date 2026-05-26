"""Dedicated tests for JwtTokenService — generation, validation, signing config."""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from services.auth_service.src.domain.entities.user import User
from services.auth_service.src.domain.exceptions.auth_errors import (
    ExpiredTokenError,
    InvalidTokenError,
)
from services.auth_service.src.domain.value_objects.jwt_config import JwtSigningConfig
from services.auth_service.src.domain.value_objects.token_payload import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
)
from services.auth_service.src.infrastructure.security.jwt_service import JwtTokenService


def _config(**overrides) -> JwtSigningConfig:
    defaults = {
        "secret_key": "test-secret-key-at-least-32-chars-long",
        "algorithm": "HS256",
        "issuer": "auth_service",
        "audience": "ai_platform",
        "access_token_ttl_seconds": 900,
        "refresh_token_ttl_seconds": 86400,
    }
    defaults.update(overrides)
    return JwtSigningConfig(**defaults)


def _service(**overrides) -> JwtTokenService:
    return JwtTokenService(_config(**overrides), allow_dev_secret=True)


def _user() -> User:
    return User.create(
        provider="github",
        provider_user_id="gh-99",
        email="jwt@example.com",
        display_name="JWT User",
    )


def test_config_rejects_empty_secret():
    with pytest.raises(ValueError, match="secret_key"):
        JwtSigningConfig(
            secret_key="",
            algorithm="HS256",
            issuer="auth",
            audience="aud",
            access_token_ttl_seconds=900,
            refresh_token_ttl_seconds=86400,
        ).validate(allow_dev_secret=True)


def test_config_rejects_unsupported_algorithm():
    with pytest.raises(ValueError, match="algorithm"):
        JwtTokenService(
            _config(algorithm="none"),
            allow_dev_secret=True,
        )


def test_config_rejects_short_secret_without_dev_flag():
    with pytest.raises(ValueError, match="32"):
        JwtTokenService(_config(secret_key="short"), allow_dev_secret=False)


def test_issue_and_validate_access_token():
    svc = _service()
    user = _user()
    token, jti = svc.issue_access_token(user, session_id="sess-a")

    claims = svc.validate_access_token(token)
    assert claims.user_id == user.id
    assert claims.email == user.email
    assert claims.session_id == "sess-a"
    assert claims.jti == jti
    assert claims.token_type == TOKEN_TYPE_ACCESS


def test_issue_and_validate_refresh_token():
    svc = _service()
    user = _user()
    token, jti = svc.issue_refresh_token(user, session_id="sess-r")

    claims = svc.validate_refresh_token(token)
    assert claims.user_id == user.id
    assert claims.session_id == "sess-r"
    assert claims.jti == jti
    assert claims.token_type == TOKEN_TYPE_REFRESH


def test_issue_token_pair_returns_both_tokens():
    svc = _service(access_token_ttl_seconds=600, refresh_token_ttl_seconds=3600)
    user = _user()
    pair = svc.issue_token_pair(user, session_id="sess-pair")

    assert pair.access_token
    assert pair.refresh_token
    assert pair.access_expires_in == 600
    assert pair.refresh_expires_in == 3600

    access = svc.validate_access_token(pair.access_token)
    refresh = svc.validate_refresh_token(pair.refresh_token)
    assert access.session_id == "sess-pair"
    assert refresh.session_id == "sess-pair"


def test_refresh_token_rejected_by_access_validator():
    svc = _service()
    user = _user()
    refresh, _ = svc.issue_refresh_token(user, session_id="s1")

    with pytest.raises(InvalidTokenError, match="access"):
        svc.validate_access_token(refresh)


def test_access_token_rejected_by_refresh_validator():
    svc = _service()
    user = _user()
    access, _ = svc.issue_access_token(user)

    with pytest.raises(InvalidTokenError, match="refresh"):
        svc.validate_refresh_token(access)


def test_expired_access_token_raises():
    svc = _service()
    user = _user()

    expired_payload = {
        "iss": "auth_service",
        "aud": "ai_platform",
        "sub": user.id,
        "iat": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
        "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
        "jti": str(uuid.uuid4()),
        "email": user.email,
        "roles": user.roles,
        "provider": user.provider,
        "token_type": TOKEN_TYPE_ACCESS,
    }
    expired = jwt.encode(
        expired_payload,
        "test-secret-key-at-least-32-chars-long",
        algorithm="HS256",
    )
    with pytest.raises(ExpiredTokenError):
        svc.validate_access_token(expired)


def test_wrong_secret_raises_invalid_token():
    svc = _service()
    other = _service(secret_key="another-secret-key-at-least-32-chars!!")
    user = _user()
    token, _ = svc.issue_access_token(user)

    with pytest.raises(InvalidTokenError):
        other.validate_access_token(token)


def test_decode_unverified_without_signature_check():
    svc = _service()
    user = _user()
    token, _ = svc.issue_access_token(user)
    payload = svc.decode_unverified(token)
    assert payload["sub"] == user.id


def test_from_settings_factory():
    svc = JwtTokenService.from_settings(
        secret_key="test-secret-key-at-least-32-chars-long",
        algorithm="HS256",
        issuer="auth_service",
        audience="ai_platform",
        access_token_ttl_seconds=900,
        refresh_token_ttl_seconds=86400,
        allow_dev_secret=True,
    )
    token, _ = svc.issue_access_token(_user())
    assert svc.validate_access_token(token).email == "jwt@example.com"
