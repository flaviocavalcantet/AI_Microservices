"""Text summarization workload runner.

Implements the ``WorkloadRunner`` port for the ``summarization`` job type.
All model logic is delegated to the ``ai_engine`` layer via
``SummarizationTask`` (which in turn drives ``HFSummarizationService``
backed by ``sshleifer/distilbart-cnn-12-6``).

This runner is responsible for the two infrastructure-layer concerns that
do not belong in the domain/application code:

1. **Model availability** — calls ``ensure_model_available()`` before the
   first ``run()`` invocation so the DistilBART weights are in the local
   HuggingFace cache before the pipeline tries to load them.

2. **Payload adaptation** — bridges the generic Celery job ``payload`` dict
   and the ``SummarizationTask`` contract, and converts the ``AIJobResult``
   back to a plain dict for the Celery result backend.

Expected ``payload`` keys
--------------------------
::

    {
        "text":           "Long document to summarise …",  # required
        "max_new_tokens": 150,   # optional – default decided by the service
        "min_new_tokens":  30,   # optional
        "max_sentences":    3,   # optional – extractive fallback sentence limit
    }

Returned dict (on success)::

    {
        "success": True,
        "data": {
            "summary":              "…",
            "original_word_count":  412,
            "summary_word_count":    87,
            "compression_ratio":    4.74,
            "truncated":            False,
        },
        "metadata": {
            "model_name": "sshleifer/distilbart-cnn-12-6",
            "latency_ms": 1823.5,
        },
    }
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from ...application.ports.workload_runner import WorkloadRunner
from ...infrastructure.capabilities.model_downloader import (
    ModelDownloadError,
    ensure_model_available,
)

logger = logging.getLogger(__name__)

# HuggingFace Hub repo used by HFSummarizationService (must stay in sync with
# ai_engine/application/services/hf_summarization_service.py DEFAULT_MODEL).
_SUMMARIZATION_MODEL_REPO = "sshleifer/distilbart-cnn-12-6"

# Lazy singleton — populated on the first run() call.
_task_instance = None


def _get_task():
    """Return a lazily-initialised ``SummarizationTask`` singleton.

    The import is deferred so that ``transformers`` and ``torch`` are not
    loaded at Celery worker start-up time — only when the first
    summarization job is actually executed.
    """
    global _task_instance
    if _task_instance is None:
        from ai_engine.application.tasks.summarization import SummarizationTask
        _task_instance = SummarizationTask()
    return _task_instance


class SummarizationWorkloadRunner(WorkloadRunner):
    """Execute text summarization via the HuggingFace DistilBART pipeline.

    The runner mirrors the structure of ``SentimentWorkloadRunner``:
    model-availability check → payload validation → execution → dict
    serialisation.
    """

    def __init__(self) -> None:
        self._model_ensured = False

    # ------------------------------------------------------------------
    # WorkloadRunner interface
    # ------------------------------------------------------------------

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # ------------------------------------------------------------------
        # 1. Ensure model weights are present in the local HF cache.
        #    ``ensure_model_available`` is idempotent — the fast path is a
        #    local-only resolve that completes in milliseconds.
        # ------------------------------------------------------------------
        if not self._model_ensured:
            try:
                ensure_model_available(_SUMMARIZATION_MODEL_REPO)
                self._model_ensured = True
            except ModelDownloadError as exc:
                logger.error("Model download failed: %s", exc)
                return {
                    "success": False,
                    "data": {},
                    "error": f"Model download failed: {exc}",
                    "metadata": {},
                }

        # ------------------------------------------------------------------
        # 2. Validate payload via the task's own validation logic so that
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
        # 3. Execute summarization and serialise the result.
        # ------------------------------------------------------------------
        result = task.execute(payload)
        return result.to_dict()
