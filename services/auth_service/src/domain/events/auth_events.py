"""Auth domain events.

Published after successful state changes.
Framework-independent dataclasses — serialised by the infrastructure layer.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class DomainEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def event_type(self) -> str:
        return self.__class__.__name__


@dataclass(frozen=True)
class UserLoggedIn(DomainEvent):
    user_id: str = ""
    email: str = ""
    provider: str = ""
    session_id: str = ""
    ip_address: str = ""


@dataclass(frozen=True)
class UserLoggedOut(DomainEvent):
    user_id: str = ""
    session_id: str = ""


@dataclass(frozen=True)
class TokenIssued(DomainEvent):
    user_id: str = ""
    jti: str = ""
    token_type: str = ""
    expires_at: str = ""


@dataclass(frozen=True)
class TokenRevoked(DomainEvent):
    user_id: str = ""
    jti: str = ""
    reason: str = ""


@dataclass(frozen=True)
class SessionCompromised(DomainEvent):
    """Emitted when refresh token theft is detected."""
    user_id: str = ""
    session_id: str = ""
    ip_address: str = ""
