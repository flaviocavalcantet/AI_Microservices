"""JWT signing configuration — injected at runtime, never hardcoded."""

from __future__ import annotations

from dataclasses import dataclass

ALLOWED_ALGORITHMS = frozenset({"HS256", "HS384", "HS512", "RS256", "RS384", "RS512"})
MIN_SECRET_LENGTH = 32


@dataclass(frozen=True)
class JwtSigningConfig:
    """Signing parameters for access and refresh JWTs."""

    secret_key: str
    algorithm: str
    issuer: str
    audience: str
    access_token_ttl_seconds: int
    refresh_token_ttl_seconds: int

    def validate(self, *, allow_dev_secret: bool = False) -> None:
        """Reject weak or invalid signing configuration."""
        if self.algorithm not in ALLOWED_ALGORITHMS:
            raise ValueError(
                f"Unsupported JWT algorithm {self.algorithm!r}. "
                f"Allowed: {', '.join(sorted(ALLOWED_ALGORITHMS))}"
            )
        if not self.secret_key:
            raise ValueError("JWT secret_key must not be empty")
        if not allow_dev_secret and len(self.secret_key) < MIN_SECRET_LENGTH:
            raise ValueError(
                f"JWT secret_key must be at least {MIN_SECRET_LENGTH} characters"
            )
        if self.access_token_ttl_seconds <= 0:
            raise ValueError("access_token_ttl_seconds must be positive")
        if self.refresh_token_ttl_seconds <= 0:
            raise ValueError("refresh_token_ttl_seconds must be positive")
