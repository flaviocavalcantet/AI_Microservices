"""shared_kernel/entities.py

Base entity class shared across all microservices.
Zero framework dependencies — pure Python dataclass mixin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class BaseEntity:
    """Common identity and audit fields for every domain entity.

    Subclass with @dataclass and call super().__init__() or rely on
    dataclass field inheritance.

    Attributes:
        id:         UUID string — the entity's stable identity.
        created_at: UTC timestamp set at creation; never mutated.
        updated_at: UTC timestamp refreshed on every save; managed by
                    the infrastructure layer (repository), NOT the entity.
    """

    id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def mark_updated(self) -> None:
        """Refresh updated_at to now.  Call from domain methods that mutate state."""
        self.updated_at = datetime.utcnow()
