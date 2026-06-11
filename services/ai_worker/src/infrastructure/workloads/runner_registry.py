"""Workload runner registry.

Maps ``job_type`` strings (as received from the Celery message) to the
concrete ``WorkloadRunner`` that can execute the corresponding AI
workload.

Adding a new job type
---------------------
1. Create a new runner module in ``infrastructure/workloads/``.
2. Add one entry to ``_RUNNER_FACTORIES`` below.

That's it — ``ai_jobs.py`` will automatically route the job to the new
runner via ``WorkloadRunnerRegistry.get()``.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict

from ...application.ports.workload_runner import WorkloadRunner
from .placeholder_runner import PlaceholderWorkloadRunner

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Factory map — add new job types here
# ---------------------------------------------------------------------------
# Each value is a zero-argument callable that returns a WorkloadRunner.
# Using lambdas keeps imports lazy so heavy ML libraries are not loaded
# until the corresponding job type is actually executed.

def _sentiment_factory() -> WorkloadRunner:
    from .sentiment_runner import SentimentWorkloadRunner
    return SentimentWorkloadRunner()


def _summarization_factory() -> WorkloadRunner:
    from .summarization_runner import SummarizationWorkloadRunner
    return SummarizationWorkloadRunner()


def _dataset_profiling_factory() -> WorkloadRunner:
    from .dataset_profiling_runner import DatasetProfilingWorkloadRunner
    return DatasetProfilingWorkloadRunner()


_RUNNER_FACTORIES: Dict[str, Callable[[], WorkloadRunner]] = {
    "sentiment_analysis": _sentiment_factory,
    "summarization":      _summarization_factory,
    "dataset_profiling":  _dataset_profiling_factory,
}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class WorkloadRunnerRegistry:
    """Resolve a ``job_type`` string to the appropriate ``WorkloadRunner``.

    Runner instances are created lazily and cached as singletons for the
    lifetime of this registry instance.  Each Celery task invocation
    creates a fresh registry, so runners are effectively per-task.

    Unknown job types fall back to ``PlaceholderWorkloadRunner``, which
    raises ``NotImplementedError`` — preserving the existing behaviour
    for unimplemented job types.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, WorkloadRunner] = {}

    def get(self, job_type: str) -> WorkloadRunner:
        """Return the runner for *job_type*, or a placeholder fallback."""
        if job_type in self._cache:
            return self._cache[job_type]

        factory = _RUNNER_FACTORIES.get(job_type)

        if factory is None:
            logger.warning(
                "No runner registered for job_type='%s' — using placeholder",
                job_type,
            )
            runner = PlaceholderWorkloadRunner()
        else:
            logger.info("Instantiating runner for job_type='%s'", job_type)
            runner = factory()

        self._cache[job_type] = runner
        return runner

    @staticmethod
    def supported_types() -> list[str]:
        """Return the list of job types that have real runner implementations."""
        return list(_RUNNER_FACTORIES.keys())
