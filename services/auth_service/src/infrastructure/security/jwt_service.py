"""JWT token service — access and refresh token generation and validation."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Tuple

import jwt

from ...application.ports.interfaces import ITokenService
from ...domain.entities.user import User
from ...domain.exceptions.auth_errors import ExpiredTokenError, InvalidTokenError
from ...domain.value_objects.jwt_config import JwtSigningConfig
from ...domain.value_objects.token_claims import RefreshTokenClaims, TokenClaims
from ...domain.value_objects.token_payload import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    AccessTokenPayload,
    IssuedTokenPair,
    RefreshTokenPayload,
)


class JwtTokenService(ITokenService):
    """Framework-independent JWT adapter using PyJWT.

    All secrets and TTLs are injected via JwtSigningConfig — nothing is hardcoded.
    """

    def __init__(
        self,
        config: JwtSigningConfig,
        *,
        allow_dev_secret: bool = False,
    ):
        config.validate(allow_dev_secret=allow_dev_secret)
        self._config = config

    @classmethod
    def from_settings(
        cls,
        *,
        secret_key: str,
        algorithm: str,
        issuer: str,
        audience: str,
        access_token_ttl_seconds: int,
        refresh_token_ttl_seconds: int,
        allow_dev_secret: bool = False,
    ) -> "JwtTokenService":
        """Factory that builds config from injected settings (e.g. Flask Config)."""
        return cls(
            JwtSigningConfig(
                secret_key=secret_key,
                algorithm=algorithm,
                issuer=issuer,
                audience=audience,
                access_token_ttl_seconds=access_token_ttl_seconds,
                refresh_token_ttl_seconds=refresh_token_ttl_seconds,
            ),
            allow_dev_secret=allow_dev_secret,
        )

    @property
    def access_token_ttl_seconds(self) -> int:
        return self._config.access_token_ttl_seconds

    @property
    def refresh_token_ttl_seconds(self) -> int:
        return self._config.refresh_token_ttl_seconds

    def issue_access_token(
        self, user: User, session_id: str | None = None
    ) -> Tuple[str, str]:
        payload = self._build_access_payload(user, session_id)
        token = self._encode(payload.to_claims_dict())
        return token, payload.jti

    def issue_refresh_token(self, user: User, session_id: str) -> Tuple[str, str]:
        payload = self._build_refresh_payload(user.id, session_id)
        token = self._encode(payload.to_claims_dict())
        return token, payload.jti

    def issue_token_pair(self, user: User, session_id: str) -> IssuedTokenPair:
        access_token, access_jti = self.issue_access_token(user, session_id=session_id)
        refresh_token, refresh_jti = self.issue_refresh_token(user, session_id)
        return IssuedTokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_jti=access_jti,
            refresh_jti=refresh_jti,
            access_expires_in=self._config.access_token_ttl_seconds,
            refresh_expires_in=self._config.refresh_token_ttl_seconds,
        )

    def validate_access_token(self, token: str) -> TokenClaims:
        payload = self._decode_and_verify(token)
        token_type = payload.get("token_type", TOKEN_TYPE_ACCESS)
        if token_type != TOKEN_TYPE_ACCESS:
            raise InvalidTokenError(
                f"Expected access token, got token_type={token_type!r}"
            )
        typed = AccessTokenPayload.from_claims_dict(payload)
        return TokenClaims(
            sub=typed.sub,
            email=typed.email,
            roles=typed.roles,
            provider=typed.provider,
            session_id=typed.session_id or "",
            jti=typed.jti,
            iss=typed.iss,
            aud=typed.aud,
            iat=datetime.fromtimestamp(typed.iat, tz=timezone.utc),
            exp=datetime.fromtimestamp(typed.exp, tz=timezone.utc),
            token_type=typed.token_type,
            display_name=typed.display_name,
            avatar_url=typed.avatar_url,
        )

    def validate_refresh_token(self, token: str) -> RefreshTokenClaims:
        payload = self._decode_and_verify(token)
        if payload.get("token_type") != TOKEN_TYPE_REFRESH:
            raise InvalidTokenError(
                f"Expected refresh token, got token_type={payload.get('token_type')!r}"
            )
        typed = RefreshTokenPayload.from_claims_dict(payload)
        return RefreshTokenClaims(
            sub=typed.sub,
            session_id=typed.session_id,
            jti=typed.jti,
            iss=typed.iss,
            aud=typed.aud,
            iat=datetime.fromtimestamp(typed.iat, tz=timezone.utc),
            exp=datetime.fromtimestamp(typed.exp, tz=timezone.utc),
            token_type=typed.token_type,
        )

    def decode_unverified(self, token: str) -> Dict[str, Any]:
        return jwt.decode(
            token,
            options={"verify_signature": False},
            algorithms=[self._config.algorithm],
        )

    def _build_access_payload(
        self, user: User, session_id: str | None
    ) -> AccessTokenPayload:
        now = datetime.now(timezone.utc)
        exp = now + timedelta(seconds=self._config.access_token_ttl_seconds)
        return AccessTokenPayload(
            sub=user.id,
            email=user.email,
            roles=list(user.roles),
            provider=user.provider,
            jti=str(uuid.uuid4()),
            iss=self._config.issuer,
            aud=self._config.audience,
            iat=int(now.timestamp()),
            exp=int(exp.timestamp()),
            token_type=TOKEN_TYPE_ACCESS,
            session_id=session_id,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
        )

    def _build_refresh_payload(self, user_id: str, session_id: str) -> RefreshTokenPayload:
        now = datetime.now(timezone.utc)
        exp = now + timedelta(seconds=self._config.refresh_token_ttl_seconds)
        return RefreshTokenPayload(
            sub=user_id,
            session_id=session_id,
            jti=str(uuid.uuid4()),
            iss=self._config.issuer,
            aud=self._config.audience,
            iat=int(now.timestamp()),
            exp=int(exp.timestamp()),
            token_type=TOKEN_TYPE_REFRESH,
        )

    def _encode(self, claims: Dict[str, Any]) -> str:
        return jwt.encode(
            claims,
            self._config.secret_key,
            algorithm=self._config.algorithm,
        )

    def _decode_and_verify(self, token: str) -> Dict[str, Any]:
        try:
            return jwt.decode(
                token,
                self._config.secret_key,
                algorithms=[self._config.algorithm],
                audience=self._config.audience,
                issuer=self._config.issuer,
                options={"require": ["exp", "iat", "sub", "jti"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise ExpiredTokenError("Token has expired.") from exc
        except jwt.InvalidTokenError as exc:
            raise InvalidTokenError(f"Invalid token: {exc}") from exc
