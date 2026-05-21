"""Event value object consumed by notification-service."""

from dataclasses import dataclass, field
from typing import Any, Dict
from uuid import uuid4


@dataclass(frozen=True)
class EventEnvelope:
    """Normalized event envelope for future event contracts."""

    event_type: str
    payload: Dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid4()))
    source: str = "unknown"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventEnvelope":
        return cls(
            event_type=data.get("event_type", "unknown"),
            payload=data.get("payload", {}),
            event_id=data.get("event_id") or data.get("id") or str(uuid4()),
            source=data.get("source", "unknown"),
        )
