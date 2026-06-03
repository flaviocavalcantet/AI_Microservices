"""
Sentiment Analysis Task (HuggingFace-backed)
============================================
Thin orchestration adapter between AIJobOrchestrator and HFSentimentService.
All model logic is encapsulated in the service; this class owns only payload
validation, result contract shaping, and error translation.

Expected payload keys
---------------------
text               (str,  required) – Text to classify.
neutral_threshold  (float, optional) – Override the service's neutral band
                                        for this call. Range: [0.0, 1.0).
                                        0.0 disables the neutral label (default).

Output AIJobResult.data keys
-----------------------------
label              (str)   – "positive" | "negative" | "neutral"
score              (float) – Confidence of the winning label in [0.0, 1.0].
scores             (dict)  – Per-label scores, e.g. {"positive": 0.9998, "negative": 0.0002}
is_neutral         (bool)  – True when neutral_threshold triggered a neutral override.
word_count         (int)   – Whitespace-token count of the input text.
input_truncated    (bool)  – True when the input exceeded the model's token limit.

Output AIJobResult.metadata keys
---------------------------------
model_name   (str)
latency_ms   (float)
"""

from __future__ import annotations

import logging
from typing import Any

from ai_engine.application.base_task import BaseAITask
from ai_engine.application.services.hf_sentiment_service import (
    HFSentimentService,
    SentimentAnalysisError,
    get_default_service,
)
from ai_engine.domain.models import AIJobResult, AIJobType

logger = logging.getLogger(__name__)

# Payload guard-rails
_MIN_CHAR_COUNT = 3       # single words / punctuation are meaningless to classify
_MAX_WORD_COUNT = 10_000  # well above the 512-token model limit; guards compute


class SentimentAnalysisTask(BaseAITask):
    """
    AI task that classifies text sentiment via a HuggingFace pipeline.

    The HFSentimentService is injected through the constructor so the task is
    fully unit-testable without a model download.

    Production usage (via container.py):
        SentimentAnalysisTask()                 # lazy singleton default service
        SentimentAnalysisTask(service=my_svc)   # injected service

    Test usage:
        SentimentAnalysisTask(service=FakeSentimentService())
    """

    job_type = AIJobType.SENTIMENT_ANALYSIS

    def __init__(self, service: HFSentimentService | None = None) -> None:
        self._service = service  # None → resolved lazily on first execute()

    # ------------------------------------------------------------------
    # BaseAITask interface
    # ------------------------------------------------------------------

    def validate_payload(self, payload: dict[str, Any]) -> None:
        text = payload.get("text", "")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Payload must contain a non-empty string 'text' field.")
        if len(text.strip()) < _MIN_CHAR_COUNT:
            raise ValueError(
                f"Text is too short for sentiment analysis ({len(text.strip())} chars). "
                f"Minimum: {_MIN_CHAR_COUNT} characters."
            )
        if len(text.split()) > _MAX_WORD_COUNT:
            raise ValueError(
                f"Text exceeds maximum allowed length ({len(text.split())} words). "
                f"Maximum: {_MAX_WORD_COUNT} words."
            )

        threshold = payload.get("neutral_threshold")
        if threshold is not None:
            if not isinstance(threshold, (int, float)):
                raise ValueError(
                    f"'neutral_threshold' must be a float in [0.0, 1.0), got: {threshold!r}."
                )
            if not (0.0 <= float(threshold) < 1.0):
                raise ValueError(
                    f"'neutral_threshold' must be in [0.0, 1.0), got: {threshold}."
                )

    def execute(self, payload: dict[str, Any]) -> AIJobResult:
        text: str = payload["text"]
        threshold: float | None = payload.get("neutral_threshold")

        service = self._get_service()

        # Apply per-request neutral threshold override when provided.
        # We create a lightweight shim rather than mutating the shared service.
        effective_service = _ThresholdShim(service, threshold) if threshold is not None else service

        try:
            output = effective_service.analyze(text)
        except SentimentAnalysisError as exc:
            logger.error("SentimentAnalysisError: %s", exc)
            return AIJobResult.failure(str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error during sentiment analysis")
            return AIJobResult.failure(f"Unexpected sentiment analysis error: {exc}")

        return AIJobResult(
            success=True,
            data={
                "label": output.label,
                "score": output.score,
                "scores": output.to_dict()["scores"],
                "is_neutral": output.is_neutral,
                "word_count": output.word_count,
                "input_truncated": output.input_truncated,
            },
            metadata={
                "model_name": output.model_name,
                "latency_ms": output.latency_ms,
            },
        )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _get_service(self) -> HFSentimentService:
        if self._service is None:
            self._service = get_default_service()
        return self._service


# ---------------------------------------------------------------------------
# Per-request threshold shim
# ---------------------------------------------------------------------------

class _ThresholdShim:
    """
    Minimal wrapper that overrides neutral_threshold on a single analyze() call
    without mutating the shared singleton service instance.
    """

    def __init__(self, service: HFSentimentService, threshold: float) -> None:
        self._service = service
        self._threshold = threshold

    def analyze(self, text: str):  # noqa: ANN201
        pipe = self._service._get_pipeline()
        clipped, truncated = self._service._maybe_clip(text, pipe)

        import time
        t0 = time.perf_counter()
        raw = pipe(clipped, top_k=None, truncation=True)
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        # Temporarily override the threshold, build the output, restore.
        original = self._service._neutral_threshold
        self._service._neutral_threshold = self._threshold
        try:
            return self._service._build_output(raw, text, latency_ms, truncated)
        finally:
            self._service._neutral_threshold = original
