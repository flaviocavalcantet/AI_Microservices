"""User domain entity.

Pure Python — no framework, no I/O.
Represents a platform user authenticated via an OAuth provider or local
username/password credentials.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


def _crypt_context():
    """Return a passlib CryptContext for bcrypt (lazy import)."""
    from passlib.context import CryptContext  # type: ignore[import]
    return CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass
class User:
    """Platform user.

    OAuth users: provider = "github" (or another provider name),
                 provider_user_id = provider's numeric/string user id.
    Local users: provider = "local",
                 provider_user_id = username (ensures uniqueness via the
                 existing (provider, provider_user_id) index).
    """

    id: str
    provider: str
    provider_user_id: str
    email: str
    display_name: str
    roles: List[str]
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None
    avatar_url: Optional[str] = None
    # Local-auth fields — None for OAuth users
    username: Optional[str] = None
    password_hash: Optional[str] = None

    @classmethod
    def create(
        cls,
        provider: str,
        provider_user_id: str,
        email: str,
        display_name: str,
        roles: Optional[List[str]] = None,
        avatar_url: Optional[str] = None,
        username: Optional[str] = None,
        password_hash: Optional[str] = None,
    ) -> "User":
        """Factory method — creates a new user with defaults."""
        return cls(
            id=str(uuid.uuid4()),
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
            display_name=display_name,
            roles=roles or ["user"],
            is_active=True,
            created_at=datetime.now(timezone.utc),
            last_login_at=datetime.now(timezone.utc),
            avatar_url=avatar_url,
            username=username,
            password_hash=password_hash,
        )

    # ------------------------------------------------------------------
    # Password helpers (local-auth users only)
    # ------------------------------------------------------------------

    def set_password(self, raw_password: str) -> None:
        """Hash *raw_password* with bcrypt and store it.  Never persists plaintext."""
        self.password_hash = _crypt_context().hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """Return True if *raw_password* matches the stored bcrypt hash."""
        if not self.password_hash:
            return False
        return _crypt_context().verify(raw_password, self.password_hash)

    # ------------------------------------------------------------------
    # Role helpers
    # ------------------------------------------------------------------

    def record_login(self) -> None:
        self.last_login_at = datetime.now(timezone.utc)

    def add_role(self, role: str) -> None:
        if role not in self.roles:
            self.roles.append(role)

    def remove_role(self, role: str) -> None:
        self.roles = [r for r in self.roles if r != role]

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def deactivate(self) -> None:
        self.is_active = False

    def is_valid(self) -> bool:
        return bool(self.id and self.provider and self.email and self.is_active)
