"""Notification domain entity."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4


@dataclass(frozen=True)
class Notification:
    """A notification request derived from an event."""

    channel: str
    event_type: str
    payload: Dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
