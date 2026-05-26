"""User domain entity.

Pure Python — no framework, no I/O.
Represents a platform user authenticated via an OAuth provider.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class User:
    """Platform user authenticated via OAuth.

    Identity is anchored to (provider, provider_user_id) — not email,
    because the same email can appear across providers.
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

    @classmethod
    def create(
        cls,
        provider: str,
        provider_user_id: str,
        email: str,
        display_name: str,
        roles: Optional[List[str]] = None,
        avatar_url: Optional[str] = None,
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
            created_at=datetime.utcnow(),
            last_login_at=datetime.utcnow(),
            avatar_url=avatar_url,
        )

    def record_login(self) -> None:
        self.last_login_at = datetime.utcnow()

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
