"""Presentation-layer auth orchestration — routes delegate here, not to use cases directly."""

from __future__ import annotations

from .....application.dto.auth_dto import (
    AuthorizationURLResponseDTO,
    OAuthCallbackDTO,
    RefreshTokenRequestDTO,
    TokenResponseDTO,
)
from .....application.use_cases.oauth_login import OAuthLoginUseCase
from .....application.use_cases.refresh_token import RefreshTokenUseCase
from .....container import resolve_from_context
from .....domain.exceptions.auth_errors import OAuthStateMismatchError
from .....infrastructure.security.oauth_registry import OAuthProviderRegistry
from .....infrastructure.security.oauth_state_store import InMemoryOAuthStateStore
from .....infrastructure.security.pkce import (
    generate_code_challenge,
    generate_code_verifier,
    generate_oauth_state,
)


class AuthApiService:
    """Coordinates OAuth flows and token operations at the HTTP boundary."""

    PROVIDER_GITHUB = "github"

    def __init__(self) -> None:
        self._config = resolve_from_context("config")

    @property
    def _registry(self) -> OAuthProviderRegistry:
        return resolve_from_context("oauth_provider_registry")

    @property
    def _state_store(self) -> InMemoryOAuthStateStore:
        return resolve_from_context("oauth_state_store")

    @property
    def _oauth_login(self) -> OAuthLoginUseCase:
        return resolve_from_context("oauth_login_use_case")

    @property
    def _refresh_token(self) -> RefreshTokenUseCase:
        return resolve_from_context("refresh_token_use_case")

    def start_oauth(
        self,
        provider: str,
        redirect_uri: str | None = None,
    ) -> AuthorizationURLResponseDTO:
        oauth_provider = self._registry.get(provider)
        state = generate_oauth_state()
        code_verifier = generate_code_verifier()
        code_challenge = generate_code_challenge(code_verifier)

        self._state_store.save(
            state=state,
            code_challenge=code_challenge,
            code_verifier=code_verifier,
            provider=provider,
            redirect_uri=redirect_uri,
        )

        return AuthorizationURLResponseDTO(
            authorization_url=oauth_provider.build_authorization_url(state, code_challenge),
            state=state,
            code_challenge=code_challenge,
            provider=provider,
            code_verifier=code_verifier,
        )

    def complete_oauth(
        self,
        provider: str,
        code: str,
        state: str,
        code_verifier: str | None,
        *,
        ip_address: str = "",
    ) -> TokenResponseDTO:
        stored = self._state_store.consume(state)
        if stored is None:
            raise OAuthStateMismatchError("Unknown or expired OAuth state.")
        if stored.provider != provider:
            raise OAuthStateMismatchError("OAuth state provider mismatch.")

        verifier = code_verifier or stored.code_verifier
        if not verifier:
            raise OAuthStateMismatchError("PKCE code_verifier is missing.")

        oauth_provider = self._registry.get(provider)
        return self._oauth_login.execute(
            provider=oauth_provider,
            callback=OAuthCallbackDTO(code=code, state=state, code_verifier=verifier),
            stored_state=stored.state,
            ip_address=ip_address,
            expires_in_seconds=self._config.JWT_ACCESS_TOKEN_SECONDS,
        )

    def login(
        self,
        provider: str,
        redirect_uri: str | None = None,
        code: str | None = None,
        state: str | None = None,
        code_verifier: str | None = None,
        *,
        ip_address: str = "",
    ) -> TokenResponseDTO | AuthorizationURLResponseDTO:
        if code and state:
            return self.complete_oauth(
                provider=provider,
                code=code,
                state=state,
                code_verifier=code_verifier,
                ip_address=ip_address,
            )
        return self.start_oauth(provider=provider, redirect_uri=redirect_uri)

    def refresh(self, refresh_token: str) -> TokenResponseDTO:
        return self._refresh_token.execute(
            RefreshTokenRequestDTO(refresh_token=refresh_token)
        )
