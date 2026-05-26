"""Typed JWT payload models — framework-independent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


@dataclass(frozen=True)
class AccessTokenPayload:
    """Claims encoded into an access JWT."""

    sub: str
    email: str
    roles: List[str]
    provider: str
    jti: str
    iss: str
    aud: str
    iat: int
    exp: int
    token_type: str = TOKEN_TYPE_ACCESS
    session_id: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None

    def to_claims_dict(self) -> Dict[str, Any]:
        claims: Dict[str, Any] = {
            "sub": self.sub,
            "email": self.email,
            "roles": list(self.roles),
            "provider": self.provider,
            "jti": self.jti,
            "iss": self.iss,
            "aud": self.aud,
            "iat": self.iat,
            "exp": self.exp,
            "token_type": self.token_type,
        }
        if self.session_id:
            claims["session_id"] = self.session_id
        if self.display_name:
            claims["display_name"] = self.display_name
        if self.avatar_url:
            claims["avatar_url"] = self.avatar_url
        return claims

    @classmethod
    def from_claims_dict(cls, data: Dict[str, Any]) -> "AccessTokenPayload":
        return cls(
            sub=data["sub"],
            email=data.get("email", ""),
            roles=list(data.get("roles", [])),
            provider=data.get("provider", ""),
            jti=data["jti"],
            iss=data.get("iss", ""),
            aud=data.get("aud", ""),
            iat=int(data["iat"]),
            exp=int(data["exp"]),
            token_type=data.get("token_type", TOKEN_TYPE_ACCESS),
            session_id=data.get("session_id"),
            display_name=data.get("display_name"),
            avatar_url=data.get("avatar_url"),
        )


@dataclass(frozen=True)
class RefreshTokenPayload:
    """Claims encoded into a refresh JWT."""

    sub: str
    session_id: str
    jti: str
    iss: str
    aud: str
    iat: int
    exp: int
    token_type: str = TOKEN_TYPE_REFRESH

    def to_claims_dict(self) -> Dict[str, Any]:
        return {
            "sub": self.sub,
            "session_id": self.session_id,
            "jti": self.jti,
            "iss": self.iss,
            "aud": self.aud,
            "iat": self.iat,
            "exp": self.exp,
            "token_type": self.token_type,
        }

    @classmethod
    def from_claims_dict(cls, data: Dict[str, Any]) -> "RefreshTokenPayload":
        return cls(
            sub=data["sub"],
            session_id=data["session_id"],
            jti=data["jti"],
            iss=data.get("iss", ""),
            aud=data.get("aud", ""),
            iat=int(data["iat"]),
            exp=int(data["exp"]),
            token_type=data.get("token_type", TOKEN_TYPE_REFRESH),
        )


@dataclass(frozen=True)
class IssuedTokenPair:
    """Access + refresh JWT pair returned from token generation."""

    access_token: str
    refresh_token: str
    access_jti: str
    refresh_jti: str
    access_expires_in: int
    refresh_expires_in: int
    token_type: str = "Bearer"
