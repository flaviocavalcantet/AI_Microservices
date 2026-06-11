"""Dataset profiling workload runner.

Implements the ``WorkloadRunner`` port for the ``dataset_profiling`` job
type.  All computation is delegated to the ``ai_engine`` layer via
``DatasetProfilingTask`` (which drives ``DatasetProfilingService``,
backed by pandas).

Unlike the model-based runners (sentiment, summarization), this runner
has **no HuggingFace model to download** — the only external dependency
is ``pandas``, which is expected to be present in the worker environment.
If it is missing, ``DatasetProfilingTask.execute()`` surfaces a clear
``DatasetProfilingImportError`` that is caught here and returned as a
structured failure dict.

Expected ``payload`` keys
--------------------------
::

    {
        "data":       "col_a,col_b\\n1,foo\\n2,bar",  # CSV string   ─┐ one of
                   or [{"col_a": 1, "col_b": "foo"}, …],             # JSON records ─┘
        "input_type": "csv" | "json" | "auto",  # optional – default "auto"
    }

Returned dict (on success)::

    {
        "success": True,
        "data": {
            "row_count":                1000,
            "column_count":               5,
            "numeric_column_count":       3,
            "categorical_column_count":   2,
            "datetime_column_count":      0,
            "mixed_column_count":         0,
            "memory_usage_bytes":     48200,
            "processing_time_ms":      12.3,
            "columns":                [...],   # per-column profiles
            "correlations":           {...},   # Pearson between numeric cols
        },
        "metadata": {
            "processing_time_ms": 12.3,
            "service_version":    "1.0.0",
        },
    }
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from ...application.ports.workload_runner import WorkloadRunner

logger = logging.getLogger(__name__)

# Lazy singleton — populated on the first run() call.
_task_instance = None


def _get_task():
    """Return a lazily-initialised ``DatasetProfilingTask`` singleton.

    The import is deferred so that ``pandas`` is not loaded at Celery
    worker start-up time — only when the first dataset-profiling job is
    executed.
    """
    global _task_instance
    if _task_instance is None:
        from ai_engine.application.tasks.dataset_profiling import DatasetProfilingTask
        _task_instance = DatasetProfilingTask()
    return _task_instance


class DatasetProfilingWorkloadRunner(WorkloadRunner):
    """Execute dataset profiling via the pandas-backed DatasetProfilingService.

    Accepts either a CSV string or a list of JSON records in the payload.
    No model download step is required — pandas is the only runtime
    dependency and its absence is surfaced as a structured failure dict
    rather than an unhandled exception.
    """

    # ------------------------------------------------------------------
    # WorkloadRunner interface
    # ------------------------------------------------------------------

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # ------------------------------------------------------------------
        # 1. Validate payload via the task's own validation logic so that
        #    error messages are consistent regardless of call site.
        # ------------------------------------------------------------------
        task = _get_task()
        try:
            task.validate_payload(payload)
        except (ValueError, TypeError) as exc:
            logger.warning("Payload validation failed: %s", exc)
            return {
                "success": False,
                "data": {},
                "error": f"Invalid payload: {exc}",
                "metadata": {},
            }

        # ------------------------------------------------------------------
        # 2. Execute profiling and serialise the result.
        #    DatasetProfilingTask.execute() catches its own errors
        #    (including DatasetProfilingImportError for missing pandas) and
        #    returns an AIJobResult with success=False, so no extra wrapping
        #    is needed here.
        # ------------------------------------------------------------------
        result = task.execute(payload)
        return result.to_dict()
