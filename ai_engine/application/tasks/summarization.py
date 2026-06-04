"""
Text Summarization Task (HuggingFace-backed)
=============================================
Thin orchestration layer that bridges the AIJobOrchestrator and the
HFSummarizationService.  All model logic lives in the service; this class
only handles payload validation, result shaping, and error translation.

Expected payload keys
---------------------
text          (str,  required) – Document to summarise.
max_new_tokens (int, optional) – Override max output tokens (default: 150).
min_new_tokens (int, optional) – Override min output tokens (default: 30).

Output AIJobResult.data keys
-----------------------------
summary              (str)
original_word_count  (int)
summary_word_count   (int)
compression_ratio    (float)
truncated            (bool)  – True if input was clipped before inference.

Output AIJobResult.metadata keys
---------------------------------
model_name   (str)
latency_ms   (float)
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from ai_engine.application.base_task import BaseAITask
from ai_engine.application.services.hf_summarization_service import (
    HFSummarizationService,
    SummarizationError,
    get_default_service,
)
from ai_engine.domain.models import AIJobResult, AIJobType

logger = logging.getLogger(__name__)

# Payload guard-rails
_MIN_WORD_COUNT = 20   # reject texts too short to summarise meaningfully
_MAX_WORD_COUNT = 50_000  # hard upper bound to prevent OOM


class SummarizationTask(BaseAITask):
    """
    AI task that produces abstractive summaries via a HuggingFace pipeline.

    The HFSummarizationService is injected through the constructor so the
    task remains fully unit-testable with a mock service – no GPU or internet
    connection required in tests.

    Production usage (via container.py):
        SummarizationTask()                  # uses singleton default service
        SummarizationTask(service=my_svc)    # inject custom service

    Test usage:
        SummarizationTask(service=FakeService())
    """

    job_type = AIJobType.SUMMARIZATION

    def __init__(
        self,
        service: HFSummarizationService | None = None,
        summariser: Callable[[str, int], str] | None = None,
    ) -> None:
        # Defer singleton resolution until first use (avoid model load at import)
        self._service = service  # None → resolved lazily in _get_service()
        self._summariser = summariser

    # ------------------------------------------------------------------
    # BaseAITask interface
    # ------------------------------------------------------------------

    def validate_payload(self, payload: dict[str, Any]) -> None:
        text = payload.get("text", "")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Payload must contain a non-empty string 'text' field.")

        word_count = len(text.split())
        if self._service is not None and word_count < _MIN_WORD_COUNT:
            raise ValueError(
                f"Text is too short to summarise ({word_count} words). "
                f"Minimum: {_MIN_WORD_COUNT} words."
            )
        if word_count > _MAX_WORD_COUNT:
            raise ValueError(
                f"Text exceeds maximum allowed length ({word_count} words). "
                f"Maximum: {_MAX_WORD_COUNT} words."
            )

        for key in ("max_new_tokens", "min_new_tokens", "max_sentences"):
            val = payload.get(key)
            if val is not None:
                if not isinstance(val, int) or val < 1:
                    raise ValueError(f"'{key}' must be a positive integer, got: {val!r}.")

    def execute(self, payload: dict[str, Any]) -> AIJobResult:
        text: str = payload["text"]
        max_new_tokens: int | None = payload.get("max_new_tokens")
        min_new_tokens: int | None = payload.get("min_new_tokens")
        max_sentences: int = payload.get("max_sentences", 3)

        service = self._get_service()

        try:
            if self._summariser is not None:
                summary = self._summariser(text, max_sentences)
                output = _summarization_output(text, summary)
            else:
                output = service.summarize(
                    text=text,
                    max_new_tokens=max_new_tokens,
                    min_new_tokens=min_new_tokens,
                )
        except SummarizationError as exc:
            if "transformers" in str(exc).lower() and self._service is service:
                output = _LightweightSummarizationService().summarize(
                    text=text,
                    max_new_tokens=max_new_tokens,
                    min_new_tokens=min_new_tokens,
                    max_sentences=max_sentences,
                )
                return AIJobResult(
                    success=True,
                    data={
                        "summary": output.summary,
                        "original_word_count": output.original_word_count,
                        "summary_word_count": output.summary_word_count,
                        "compression_ratio": output.compression_ratio,
                        "truncated": output.truncated,
                    },
                    metadata={
                        "model_name": output.model_name,
                        "latency_ms": output.latency_ms,
                    },
                )
            logger.error("SummarizationError: %s", exc)
            return AIJobResult.failure(str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error during summarization")
            return AIJobResult.failure(f"Unexpected summarization error: {exc}")

        return AIJobResult(
            success=True,
            data={
                "summary": output.summary,
                "original_word_count": output.original_word_count,
                "summary_word_count": output.summary_word_count,
                "compression_ratio": output.compression_ratio,
                "truncated": output.truncated,
            },
            metadata={
                "model_name": output.model_name,
                "latency_ms": output.latency_ms,
            },
        )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _get_service(self) -> HFSummarizationService:
        if self._service is None:
            self._service = get_default_service()
        return self._service


@dataclass(frozen=True)
class _LightweightSummarizationOutput:
    summary: str
    original_word_count: int
    summary_word_count: int
    compression_ratio: float
    model_name: str
    latency_ms: float
    truncated: bool = False


def _summarization_output(text: str, summary: str, latency_ms: float = 0.0) -> _LightweightSummarizationOutput:
    original_word_count = len(text.split())
    summary_word_count = len(summary.split())
    compression_ratio = (
        round(original_word_count / summary_word_count, 4) if summary_word_count else 0.0
    )
    return _LightweightSummarizationOutput(
        summary=summary,
        original_word_count=original_word_count,
        summary_word_count=summary_word_count,
        compression_ratio=compression_ratio,
        model_name="lightweight-extractive",
        latency_ms=latency_ms,
    )


class _LightweightSummarizationService:
    def summarize(
        self,
        text: str,
        max_new_tokens: int | None = None,
        min_new_tokens: int | None = None,
        max_sentences: int = 3,
    ) -> _LightweightSummarizationOutput:
        start = time.perf_counter()
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", text.strip())
            if sentence.strip()
        ]
        if not sentences:
            sentences = [text.strip()]
        summary = " ".join(sentences[:max_sentences])
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return _summarization_output(text, summary, latency_ms=latency_ms)
