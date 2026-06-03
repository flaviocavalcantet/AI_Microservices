"""
Repository interfaces (ports) – pure abstractions, no framework.

Concrete adapters live in ai_engine/infrastructure/persistence/.

Two parallel port families are defined here:
- AIJobRepository      – synchronous port (pymongo, in-memory stubs, …)
- AsyncAIJobRepository – asyncio-native port (Motor, aiosqlite, …)

The domain layer imports only these ABCs; concrete adapters live in
infrastructure/persistence/ and are wired by the DI container.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ai_engine.domain.models import AIJob, AIJobStatus


# ---------------------------------------------------------------------------
# Synchronous port (unchanged)
# ---------------------------------------------------------------------------

class AIJobRepository(ABC):
    """Synchronous port that infrastructure adapters must implement."""

    @abstractmethod
    def save(self, job: AIJob) -> None: ...

    @abstractmethod
    def get_by_id(self, job_id: str) -> Optional[AIJob]: ...

    @abstractmethod
    def list_by_status(self, status: AIJobStatus) -> list[AIJob]: ...

    @abstractmethod
    def update(self, job: AIJob) -> None: ...


# ---------------------------------------------------------------------------
# Asynchronous port
# ---------------------------------------------------------------------------

class AsyncAIJobRepository(ABC):
    """
    Asyncio-native port for AI job persistence.

    Concrete adapters (e.g. MotorAIJobRepository) implement this interface.
    All methods are coroutines and must be awaited by callers.
    """

    @abstractmethod
    async def save(self, job: AIJob) -> None:
        """Persist a new job.  Raises ValueError if job_id already exists."""
        ...

    @abstractmethod
    async def get_by_id(self, job_id: str) -> Optional[AIJob]:
        """Return the job or None if not found."""
        ...

    @abstractmethod
    async def list_by_status(
        self,
        status: AIJobStatus,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AIJob]:
        """
        Return jobs with the given status, ordered by created_at ascending.

        The limit/offset parameters guard against unbounded result sets.
        """
        ...

    @abstractmethod
    async def update(self, job: AIJob) -> None:
        """Overwrite the stored job.  Raises ValueError if not found."""
        ...
