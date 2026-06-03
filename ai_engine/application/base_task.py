"""
Abstract AI task contracts.

Two parallel families:
- BaseAITask      – synchronous execution contract (existing tasks unchanged)
- AsyncBaseAITask – asyncio-native execution contract for I/O-bound or
                    network-backed tasks (remote model APIs, async databases…)

Every concrete async task must:
1. Inherit from AsyncBaseAITask.
2. Declare which AIJobType it handles via the `job_type` class variable.
3. Implement `async def execute(payload) → AIJobResult`.

The AsyncAIJobOrchestrator dispatches by matching AIJobType against a registry
of AsyncBaseAITask instances, identical to the sync pattern.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from ai_engine.domain.models import AIJobResult, AIJobType


# ---------------------------------------------------------------------------
# Synchronous contract (unchanged)
# ---------------------------------------------------------------------------

class BaseAITask(ABC):
    """
    Reusable execution contract for every AI task.

    Design notes:
    - Stateless by convention: all inputs come through `payload`.
    - `execute` must be idempotent for safe retry scenarios.
    - Heavy I/O (model calls, DB reads) belongs here, not in the domain layer.
    """

    job_type: ClassVar[AIJobType]

    @abstractmethod
    def execute(self, payload: dict[str, Any]) -> AIJobResult:
        """
        Run the AI task.

        Args:
            payload: Validated, task-specific input dict from AIJob.payload.

        Returns:
            AIJobResult with success=True and populated `data`, or
            AIJobResult with success=False and a descriptive `error`.

        Raises:
            Should NOT raise – catch all exceptions internally and return
            AIJobResult.failure(…) so the orchestrator can handle them
            uniformly.
        """
        ...

    def validate_payload(self, payload: dict[str, Any]) -> None:
        """
        Optional lightweight payload validation before execution.

        Raise ValueError with a descriptive message if invalid.
        Default implementation is a no-op.
        """


# ---------------------------------------------------------------------------
# Asynchronous contract
# ---------------------------------------------------------------------------

class AsyncBaseAITask(ABC):
    """
    Asyncio-native execution contract for I/O-bound AI tasks.

    Design notes:
    - Stateless by convention: all inputs come through `payload`.
    - `execute` must be a coroutine and must not block the event loop.
      Wrap any unavoidable blocking calls with asyncio.to_thread().
    - `execute` must be idempotent for safe retry scenarios.
    - Validation is also async to allow lightweight remote schema checks
      if needed; most implementations will stay synchronous internally.
    """

    job_type: ClassVar[AIJobType]

    @abstractmethod
    async def execute(self, payload: dict[str, Any]) -> AIJobResult:
        """
        Run the AI task as a coroutine.

        Args:
            payload: Validated, task-specific input dict from AIJob.payload.

        Returns:
            AIJobResult with success=True and populated `data`, or
            AIJobResult with success=False and a descriptive `error`.

        Raises:
            Should NOT raise – catch all exceptions internally and return
            AIJobResult.failure(…) so the orchestrator handles them uniformly.
        """
        ...

    async def validate_payload(self, payload: dict[str, Any]) -> None:
        """
        Optional async payload validation before execution.

        Raise ValueError with a descriptive message if invalid.
        Default implementation is a no-op.

        Making this async allows I/O-backed validation (e.g. checking a
        referenced resource exists) without blocking the event loop.
        """
