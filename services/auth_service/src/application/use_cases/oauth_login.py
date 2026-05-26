"""OAuth login use case."""

from __future__ import annotations

import uuid

from ...domain.entities.refresh_token import RefreshToken
from ...domain.entities.user import User
from ...domain.events.auth_events import TokenIssued, UserLoggedIn
from ...domain.exceptions.auth_errors import OAuthProviderError, OAuthStateMismatchError, UserInactiveError
from ..dto.auth_dto import OAuthCallbackDTO, TokenResponseDTO
from ..ports.interfaces import IEventPublisher, IOAuthProvider, IRefreshTokenRepository, ITokenService, IUserRepository

import logging

logger = logging.getLogger(__name__)


class OAuthLoginUseCase:
    """Handles the OAuth provider callback and issues a platform token pair."""

    def __init__(
        self,
        token_service: ITokenService,
        user_repository: IUserRepository,
        refresh_token_repository: IRefreshTokenRepository,
        event_publisher: IEventPublisher,
        refresh_token_ttl_days: int = 30,
    ) -> None:
        self._tokens = token_service
        self._users = user_repository
        self._refresh_tokens = refresh_token_repository
        self._events = event_publisher
        self._refresh_ttl_days = refresh_token_ttl_days

    def execute(
        self,
        provider: IOAuthProvider,
        callback: OAuthCallbackDTO,
        stored_state: str,
        ip_address: str = "",
        expires_in_seconds: int = 900,
    ) -> TokenResponseDTO:
        self._validate_state(callback.state, stored_state)
        userinfo = self._exchange_code(provider, callback)
        user = self._resolve_user(provider.name, userinfo)
        session_id = str(uuid.uuid4())
        access_token, jti = self._tokens.issue_access_token(user, session_id=session_id)
        refresh_entity, raw_refresh = RefreshToken.create(
            user_id=user.id, session_id=session_id, ttl_days=self._refresh_ttl_days,
        )
        self._refresh_tokens.save(refresh_entity)
        self._publish_events(user, session_id, jti, ip_address)
        logger.info("OAuth login successful", extra={"user_id": user.id, "provider": provider.name})
        return TokenResponseDTO(access_token=access_token, refresh_token=raw_refresh, expires_in=expires_in_seconds)

    def _validate_state(self, received: str, stored: str) -> None:
        if not received or received != stored:
            logger.warning("OAuth state mismatch — possible CSRF attempt")
            raise OAuthStateMismatchError("State parameter mismatch. Request may be forged.")

    def _exchange_code(self, provider: IOAuthProvider, callback: OAuthCallbackDTO) -> dict:
        try:
            return provider.exchange_code(code=callback.code, state=callback.state, code_verifier=callback.code_verifier)
        except Exception as exc:
            logger.error("OAuth code exchange failed", extra={"provider": provider.name, "error": str(exc)})
            raise OAuthProviderError(f"Code exchange failed with {provider.name}: {exc}") from exc

    def _resolve_user(self, provider_name: str, userinfo: dict) -> User:
        existing = self._users.find_by_provider(provider_name, userinfo["provider_user_id"])
        if existing:
            if not existing.is_active:
                raise UserInactiveError(existing.id)
            existing.record_login()
            return self._users.save(existing)
        new_user = User.create(
            provider=provider_name,
            provider_user_id=userinfo["provider_user_id"],
            email=userinfo["email"],
            display_name=userinfo.get("display_name", userinfo["email"]),
            avatar_url=userinfo.get("avatar_url"),
        )
        return self._users.save(new_user)

    def _publish_events(self, user: User, session_id: str, jti: str, ip_address: str) -> None:
        try:
            self._events.publish(UserLoggedIn(user_id=user.id, email=user.email, provider=user.provider, session_id=session_id, ip_address=ip_address))
            self._events.publish(TokenIssued(user_id=user.id, jti=jti, token_type="access", expires_at=""))
        except Exception as exc:
            logger.warning("Failed to publish login events (non-fatal)", extra={"error": str(exc)})
