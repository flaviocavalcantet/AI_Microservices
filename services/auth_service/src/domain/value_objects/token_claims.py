"""Auth domain value objects."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional


@dataclass(frozen=True)
class Email:
    """Email address value object — validates on construction."""

    value: str

    _PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    def __post_init__(self) -> None:
        if not self._PATTERN.match(self.value):
            raise ValueError(f"Invalid email address: {self.value!r}")

    def __str__(self) -> str:
        return self.value

    @property
    def domain(self) -> str:
        return self.value.split("@", 1)[1]


@dataclass(frozen=True)
class TokenClaims:
    """Validated access JWT payload — produced after signature verification.

    Immutable: represents trusted, decoded claims.
    Created only by JwtTokenService after successful validation.
    """

    sub: str
    email: str
    roles: List[str]
    provider: str
    session_id: str
    jti: str
    iss: str
    aud: str
    iat: datetime
    exp: datetime
    token_type: str = "access"
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_any_role(self, *roles: str) -> bool:
        return any(r in self.roles for r in roles)

    @property
    def user_id(self) -> str:
        return self.sub

    @property
    def is_expired(self) -> bool:
        now = datetime.now(timezone.utc)
        exp = self.exp if self.exp.tzinfo else self.exp.replace(tzinfo=timezone.utc)
        return now > exp


@dataclass(frozen=True)
class RefreshTokenClaims:
    """Validated refresh JWT payload."""

    sub: str
    session_id: str
    jti: str
    iss: str
    aud: str
    iat: datetime
    exp: datetime
    token_type: str = "refresh"

    @property
    def user_id(self) -> str:
        return self.sub

    @property
    def is_expired(self) -> bool:
        now = datetime.now(timezone.utc)
        exp = self.exp if self.exp.tzinfo else self.exp.replace(tzinfo=timezone.utc)
        return now > exp
