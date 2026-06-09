"""Sentiment analysis workload runner.

Implements the ``WorkloadRunner`` port for the ``sentiment_analysis``
job type.  All model interaction is delegated to the ``ai_engine``
layer which already contains the HuggingFace pipeline wrapper
(``HFSentimentService``) and orchestration adapter
(``SentimentAnalysisTask``).

This runner adds two responsibilities that belong to the celery-worker
infrastructure layer rather than the domain/application layer:

1. **Model availability** — calls ``ensure_model_available()`` on the
   first ``run()`` invocation to download the DistilBERT weights if
   they are not already cached.

2. **Payload adaptation** — translates between the generic Celery job
   ``payload`` dict and the ``SentimentAnalysisTask`` contract, and
   converts the ``AIJobResult`` back to a plain dict for the Celery
   result backend.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from ...application.ports.workload_runner import WorkloadRunner
from ...infrastructure.capabilities.model_downloader import (
    ensure_model_available,
    ModelDownloadError,
)

logger = logging.getLogger(__name__)

# HuggingFace model used by the sentiment service.
_SENTIMENT_MODEL_REPO = "distilbert-base-uncased-finetuned-sst-2-english"

# Lazy singleton — populated on first run().
_task_instance = None


def _get_task():
    """Return a lazily-initialised SentimentAnalysisTask singleton.

    The import is deferred so that ``transformers`` and ``torch`` are
    not loaded at Celery worker import time — only when the first
    sentiment job is actually executed.
    """
    global _task_instance
    if _task_instance is None:
        from ai_engine.application.tasks.sentiment_analysis import (
            SentimentAnalysisTask,
        )
        _task_instance = SentimentAnalysisTask()
    return _task_instance


class SentimentWorkloadRunner(WorkloadRunner):
    """Execute sentiment analysis via the HuggingFace DistilBERT pipeline.

    Expected ``payload`` keys::

        {
            "text": "The product is absolutely fantastic!",
            "neutral_threshold": 0.15   # optional
        }

    Returns a dict serialisation of ``AIJobResult`` on success, or a
    failure dict with ``success=False`` and an error message.
    """

    def __init__(self) -> None:
        self._model_ensured = False

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # ------------------------------------------------------------------
        # 1. Ensure model weights are downloaded (idempotent / fast path)
        # ------------------------------------------------------------------
        if not self._model_ensured:
            try:
                ensure_model_available(_SENTIMENT_MODEL_REPO)
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
        # 2. Validate payload
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
        # 3. Execute sentiment analysis
        # ------------------------------------------------------------------
        result = task.execute(payload)
        return result.to_dict()
