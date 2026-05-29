"""shared_kernel/repositories.py

Base repository abstractions shared across all microservices.
Framework-independent — pure Python ABCs.

These are the canonical contracts every infrastructure adapter must satisfy.
Services import from here; infrastructure layers implement them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, List, Optional, Tuple, TypeVar

# T = the domain entity type (e.g. User, Job, AIProcessingResult)
T = TypeVar("T")
ID = TypeVar("ID")


class IRepository(ABC, Generic[T]):
    """Minimal generic repository contract.

    Concrete domain interfaces (IJobRepository, IUserRepository …) may extend
    this or define their own signatures — this exists only to establish the
    pattern and allow shared utilities to accept any repository type.
    """

    @abstractmethod
    def save(self, entity: T) -> T:
        """Persist entity (insert or upsert)."""

    @abstractmethod
    def find_by_id(self, entity_id: str) -> Optional[T]:
        """Return entity by primary key, or None."""

    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        """Remove entity. Returns True if deleted, False if not found."""

    @abstractmethod
    def exists(self, entity_id: str) -> bool:
        """Return True if an entity with the given id exists."""


class IPageableRepository(IRepository[T], Generic[T]):
    """Repository extension for paginated list queries."""

    @abstractmethod
    def find_all(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[T], int]:
        """Return (page_of_entities, total_count)."""
