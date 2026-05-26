"""Tests for JWT service and auth use cases."""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from services.auth_service.src.application.dto.auth_dto import (
    OAuthCallbackDTO,
    RefreshTokenRequestDTO,
    RevokeTokenRequestDTO,
    TokenVerifyRequestDTO,
)
from services.auth_service.src.application.use_cases.oauth_login import OAuthLoginUseCase
from services.auth_service.src.application.use_cases.refresh_token import RefreshTokenUseCase
from services.auth_service.src.application.use_cases.token_ops import (
    RevokeTokenUseCase,
    ValidateTokenUseCase,
)
from services.auth_service.src.domain.entities.user import User
from services.auth_service.src.domain.exceptions.auth_errors import (
    RevokedTokenError,
    TokenFamilyCompromisedError,
)
from services.auth_service.src.infrastructure.events.noop_publisher import NoOpEventPublisher
from services.auth_service.src.infrastructure.repositories.in_memory_refresh_token_repository import (
    InMemoryRefreshTokenRepository,
)
from services.auth_service.src.infrastructure.repositories.in_memory_user_repository import (
    InMemoryUserRepository,
)
from services.auth_service.src.infrastructure.security.jwt_service import JwtTokenService
from services.auth_service.src.infrastructure.security.pkce import (
    generate_code_challenge,
    generate_code_verifier,
)


class FakeOAuthProvider:
    name = "github"

    def build_authorization_url(self, state: str, code_challenge: str) -> str:
        return f"https://example.com/oauth?state={state}"

    def exchange_code(self, code: str, state: str, code_verifier: str) -> dict:
        return {
            "provider_user_id": "gh-123",
            "email": "dev@example.com",
            "display_name": "Dev User",
            "avatar_url": None,
        }

    def get_userinfo(self, access_token: str) -> dict:
        return self.exchange_code("", "", "")


@pytest.fixture
def token_service():
    return JwtTokenService.from_settings(
        secret_key="test-secret-key-at-least-32-chars-long",
        algorithm="HS256",
        issuer="auth_service",
        audience="ai_platform",
        access_token_ttl_seconds=900,
        refresh_token_ttl_seconds=86400,
        allow_dev_secret=True,
    )


@pytest.fixture
def repos():
    return InMemoryUserRepository(), InMemoryRefreshTokenRepository()


def test_issue_and_validate_access_token(token_service):
    user = User.create(
        provider="github",
        provider_user_id="gh-1",
        email="a@example.com",
        display_name="A",
    )
    token, jti = token_service.issue_access_token(user, session_id="sess-1")

    assert jti
    claims = token_service.validate_access_token(token)
    assert claims.user_id == user.id
    assert claims.email == user.email
    assert claims.roles == ["user"]
    assert claims.session_id == "sess-1"


def test_expired_token_raises(token_service):
    user = User.create(
        provider="github",
        provider_user_id="gh-2",
        email="b@example.com",
        display_name="B",
    )
    now = datetime.now(timezone.utc)
    payload = {
        "iss": "auth_service",
        "aud": "ai_platform",
        "sub": user.id,
        "iat": int((now - timedelta(hours=2)).timestamp()),
        "exp": int((now - timedelta(hours=1)).timestamp()),
        "jti": str(uuid.uuid4()),
        "email": user.email,
        "roles": user.roles,
        "provider": user.provider,
    }
    expired = jwt.encode(
        payload, "test-secret-key-at-least-32-chars-long", algorithm="HS256"
    )

    from services.auth_service.src.domain.exceptions.auth_errors import ExpiredTokenError

    with pytest.raises(ExpiredTokenError):
        token_service.validate_access_token(expired)


def test_oauth_login_issues_token_pair(token_service, repos):
    users, refresh_repo = repos
    use_case = OAuthLoginUseCase(
        token_service=token_service,
        user_repository=users,
        refresh_token_repository=refresh_repo,
        event_publisher=NoOpEventPublisher(),
        refresh_token_ttl_days=30,
    )
    provider = FakeOAuthProvider()
    state = "csrf-state-123"
    result = use_case.execute(
        provider=provider,
        callback=OAuthCallbackDTO(
            code="auth-code",
            state=state,
            code_verifier=generate_code_verifier(),
        ),
        stored_state=state,
    )

    assert result.access_token
    assert result.refresh_token
    assert result.expires_in == 900
    claims = token_service.validate_access_token(result.access_token)
    assert claims.email == "dev@example.com"


def test_refresh_token_rotation(token_service, repos):
    users, refresh_repo = repos
    login = OAuthLoginUseCase(
        token_service=token_service,
        user_repository=users,
        refresh_token_repository=refresh_repo,
        event_publisher=NoOpEventPublisher(),
    )
    provider = FakeOAuthProvider()
    state = "state-rotate"
    first = login.execute(
        provider=provider,
        callback=OAuthCallbackDTO(code="c", state=state, code_verifier="v"),
        stored_state=state,
    )

    refresh_uc = RefreshTokenUseCase(
        token_service=token_service,
        user_repository=users,
        refresh_token_repository=refresh_repo,
        event_publisher=NoOpEventPublisher(),
    )
    second = refresh_uc.execute(RefreshTokenRequestDTO(refresh_token=first.refresh_token))

    assert second.access_token != first.access_token
    assert second.refresh_token != first.refresh_token

    with pytest.raises(TokenFamilyCompromisedError):
        refresh_uc.execute(RefreshTokenRequestDTO(refresh_token=first.refresh_token))


def test_revoked_token_reuse_invalidates_family(token_service, repos):
    users, refresh_repo = repos
    login = OAuthLoginUseCase(
        token_service=token_service,
        user_repository=users,
        refresh_token_repository=refresh_repo,
        event_publisher=NoOpEventPublisher(),
    )
    provider = FakeOAuthProvider()
    state = "state-compromise"
    tokens = login.execute(
        provider=provider,
        callback=OAuthCallbackDTO(code="c", state=state, code_verifier="v"),
        stored_state=state,
    )

    refresh_uc = RefreshTokenUseCase(
        token_service=token_service,
        user_repository=users,
        refresh_token_repository=refresh_repo,
        event_publisher=NoOpEventPublisher(),
    )
    rotated = refresh_uc.execute(
        RefreshTokenRequestDTO(refresh_token=tokens.refresh_token)
    )

    with pytest.raises(TokenFamilyCompromisedError):
        refresh_uc.execute(RefreshTokenRequestDTO(refresh_token=tokens.refresh_token))

    with pytest.raises((RevokedTokenError, TokenFamilyCompromisedError)):
        refresh_uc.execute(RefreshTokenRequestDTO(refresh_token=rotated.refresh_token))


def test_validate_and_revoke_use_cases(token_service, repos):
    users, refresh_repo = repos
    login = OAuthLoginUseCase(
        token_service=token_service,
        user_repository=users,
        refresh_token_repository=refresh_repo,
        event_publisher=NoOpEventPublisher(),
    )
    provider = FakeOAuthProvider()
    state = "state-verify"
    tokens = login.execute(
        provider=provider,
        callback=OAuthCallbackDTO(code="c", state=state, code_verifier="v"),
        stored_state=state,
    )

    verify = ValidateTokenUseCase(token_service)
    ok = verify.execute(TokenVerifyRequestDTO(token=tokens.access_token))
    assert ok.valid is True
    assert ok.user_id

    RevokeTokenUseCase(refresh_repo, NoOpEventPublisher()).execute(
        RevokeTokenRequestDTO(refresh_token=tokens.refresh_token)
    )

    refresh_uc = RefreshTokenUseCase(
        token_service=token_service,
        user_repository=users,
        refresh_token_repository=refresh_repo,
        event_publisher=NoOpEventPublisher(),
    )
    with pytest.raises(TokenFamilyCompromisedError):
        refresh_uc.execute(RefreshTokenRequestDTO(refresh_token=tokens.refresh_token))


def test_pkce_challenge_is_deterministic():
    verifier = generate_code_verifier()
    assert generate_code_challenge(verifier) == generate_code_challenge(verifier)
