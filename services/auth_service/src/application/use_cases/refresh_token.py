"""Refresh token use case — implements refresh token rotation."""

from __future__ import annotations

from ...domain.entities.refresh_token import RefreshToken
from ...domain.events.auth_events import TokenIssued
from ...domain.exceptions.auth_errors import (
    ExpiredTokenError, RevokedTokenError, TokenFamilyCompromisedError,
    UserInactiveError, UserNotFoundError,
)
from ..dto.auth_dto import RefreshTokenRequestDTO, TokenResponseDTO
from ..ports.interfaces import IEventPublisher, IRefreshTokenRepository, ITokenService, IUserRepository

import logging

logger = logging.getLogger(__name__)


class RefreshTokenUseCase:
    """Rotate a refresh token and issue a new access + refresh pair."""

    def __init__(
        self,
        token_service: ITokenService,
        user_repository: IUserRepository,
        refresh_token_repository: IRefreshTokenRepository,
        event_publisher: IEventPublisher,
        refresh_token_ttl_days: int = 30,
        expires_in_seconds: int = 900,
    ) -> None:
        self._tokens = token_service
        self._users = user_repository
        self._refresh_tokens = refresh_token_repository
        self._events = event_publisher
        self._refresh_ttl_days = refresh_token_ttl_days
        self._expires_in = expires_in_seconds

    def execute(self, request: RefreshTokenRequestDTO) -> TokenResponseDTO:
        token_hash = RefreshToken.hash(request.refresh_token)
        stored = self._refresh_tokens.find_by_hash(token_hash)

        if stored is None:
            raise RevokedTokenError("Refresh token not found.")

        if stored.is_revoked:
            logger.warning("Revoked refresh token presented — possible theft", extra={"session_id": stored.session_id})
            self._refresh_tokens.revoke_session(stored.session_id, "compromised_reuse")
            raise TokenFamilyCompromisedError(stored.session_id)

        if stored.is_expired:
            raise ExpiredTokenError("Refresh token has expired.")

        user = self._users.find_by_id(stored.user_id)
        if user is None:
            raise UserNotFoundError(stored.user_id)
        if not user.is_active:
            raise UserInactiveError(user.id)

        new_refresh_entity, raw_new_refresh = RefreshToken.create(
            user_id=user.id, session_id=stored.session_id, ttl_days=self._refresh_ttl_days,
        )
        self._refresh_tokens.save(new_refresh_entity)
        stored.mark_used(replaced_by_id=new_refresh_entity.id)
        stored.revoke(reason="rotated")
        self._refresh_tokens.save(stored)

        access_token, jti = self._tokens.issue_access_token(user, session_id=stored.session_id)

        try:
            self._events.publish(TokenIssued(user_id=user.id, jti=jti, token_type="access", expires_at=""))
        except Exception as exc:
            logger.warning("Failed to publish TokenIssued event", extra={"error": str(exc)})

        logger.info("Refresh token rotated", extra={"user_id": user.id, "session_id": stored.session_id})
        return TokenResponseDTO(access_token=access_token, refresh_token=raw_new_refresh, expires_in=self._expires_in)
