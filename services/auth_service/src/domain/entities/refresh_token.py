"""RefreshToken domain entity.

Opaque refresh tokens stored server-side.
Rotation strategy: every use invalidates the token and issues a new one.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class RefreshToken:
    """Opaque refresh token tied to a user session.

    Token families: all tokens in a family share a session_id.
    If a revoked token is presented, the entire family is invalidated
    (detects refresh token theft).
    """

    id: str
    token_hash: str
    user_id: str
    session_id: str
    expires_at: datetime
    created_at: datetime
    used_at: Optional[datetime]
    revoked_at: Optional[datetime]
    revoked_reason: Optional[str]
    replaced_by_id: Optional[str]

    @classmethod
    def create(
        cls,
        user_id: str,
        session_id: str,
        ttl_days: int = 30,
    ) -> tuple["RefreshToken", str]:
        """Create a new refresh token.

        Returns:
            Tuple of (RefreshToken entity, raw token string).
            The raw token is returned only at creation — never stored.
        """
        raw_token = secrets.token_urlsafe(64)
        token_hash = cls._hash_token(raw_token)
        now = datetime.utcnow()

        entity = cls(
            id=str(uuid.uuid4()),
            token_hash=token_hash,
            user_id=user_id,
            session_id=session_id,
            expires_at=now + timedelta(days=ttl_days),
            created_at=now,
            used_at=None,
            revoked_at=None,
            revoked_reason=None,
            replaced_by_id=None,
        )
        return entity, raw_token

    @staticmethod
    def _hash_token(raw_token: str) -> str:
        """SHA-256 hash — only the hash is persisted."""
        import hashlib
        return hashlib.sha256(raw_token.encode()).hexdigest()

    @classmethod
    def hash(cls, raw_token: str) -> str:
        return cls._hash_token(raw_token)

    def is_valid(self) -> bool:
        return (
            self.revoked_at is None
            and self.expires_at > datetime.utcnow()
        )

    def mark_used(self, replaced_by_id: str) -> None:
        self.used_at = datetime.utcnow()
        self.replaced_by_id = replaced_by_id

    def revoke(self, reason: str = "explicit_revocation") -> None:
        self.revoked_at = datetime.utcnow()
        self.revoked_reason = reason

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= datetime.utcnow()

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None
