"""Token revocation and validation use cases."""

from __future__ import annotations

from ...domain.entities.refresh_token import RefreshToken
from ...domain.events.auth_events import UserLoggedOut
from ...domain.value_objects.token_claims import TokenClaims
from ..dto.auth_dto import RevokeTokenRequestDTO, TokenVerifyRequestDTO, TokenVerifyResponseDTO
from ..ports.interfaces import IEventPublisher, IRefreshTokenRepository, ITokenService

import logging

logger = logging.getLogger(__name__)


class RevokeTokenUseCase:
    """Revoke a refresh token and its entire session family (logout)."""

    def __init__(self, refresh_token_repository: IRefreshTokenRepository, event_publisher: IEventPublisher) -> None:
        self._refresh_tokens = refresh_token_repository
        self._events = event_publisher

    def execute(self, request: RevokeTokenRequestDTO) -> None:
        token_hash = RefreshToken.hash(request.refresh_token)
        stored = self._refresh_tokens.find_by_hash(token_hash)
        if stored is None or stored.is_revoked:
            return
        revoked_count = self._refresh_tokens.revoke_session(stored.session_id, reason=request.reason or "user_logout")
        try:
            self._events.publish(UserLoggedOut(user_id=stored.user_id, session_id=stored.session_id))
        except Exception as exc:
            logger.warning("Failed to publish logout event", extra={"error": str(exc)})
        logger.info("Session revoked", extra={"user_id": stored.user_id, "session_id": stored.session_id, "revoked_count": revoked_count})


class ValidateTokenUseCase:
    """Validate an access token and return its claims."""

    def __init__(self, token_service: ITokenService) -> None:
        self._tokens = token_service

    def execute(self, request: TokenVerifyRequestDTO) -> TokenVerifyResponseDTO:
        try:
            claims: TokenClaims = self._tokens.validate_access_token(request.token)
            return TokenVerifyResponseDTO(
                valid=True, user_id=claims.user_id, email=claims.email,
                roles=claims.roles, expires_at=claims.exp.isoformat() + "Z",
            )
        except Exception as exc:
            logger.debug("Token validation failed", extra={"error": str(exc)})
            return TokenVerifyResponseDTO(valid=False, error=str(exc))
