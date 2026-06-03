"""
HuggingFace Summarization Service
==================================
A reusable, framework-independent service that wraps the
`sshleifer/distilbart-cnn-12-6` model (or any seq2seq summariser).

Design decisions
----------------
- **Lazy singleton loading**: the pipeline is built on the first call to
  `summarize()`, not at import time.  Flask workers that never receive a
  summarization request pay zero memory cost.
- **Thread-safe initialisation**: a threading.Lock guards the one-time
  model load so concurrent requests don't race to build the pipeline.
- **CPU-friendly defaults**: `device=-1` forces CPU; `torch_dtype` is left
  as default (fp32) for maximum compatibility.
- **Configurable via constructor**: model name, token limits, and device are
  all injectable – swap in a GPU path or a different model without touching
  any other file.
- **Structured result**: returns a `SummarizationOutput` dataclass so callers
  get IDE auto-complete and type safety, not raw dicts.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Default model – small enough to run comfortably on CPU (~900 MB fp32).
DEFAULT_MODEL = "sshleifer/distilbart-cnn-12-6"

# Hard token-length guard-rails that keep inference fast on CPU.
_MIN_NEW_TOKENS = 30
_MAX_NEW_TOKENS_DEFAULT = 150  # roughly 100-120 English words


# ---------------------------------------------------------------------------
# Structured output
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SummarizationOutput:
    """
    Immutable result returned by HFSummarizationService.summarize().

    Attributes:
        summary:             The generated summary text.
        original_word_count: Word count of the source text.
        summary_word_count:  Word count of the generated summary.
        compression_ratio:   original / summary word count (higher = more compressed).
        model_name:          Name of the model that produced the summary.
        latency_ms:          Wall-clock time for the pipeline call in milliseconds.
        truncated:           True when the input was longer than max_input_tokens
                             and was silently clipped before being sent to the model.
    """

    summary: str
    original_word_count: int
    summary_word_count: int
    compression_ratio: float
    model_name: str
    latency_ms: float
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "original_word_count": self.original_word_count,
            "summary_word_count": self.summary_word_count,
            "compression_ratio": self.compression_ratio,
            "model_name": self.model_name,
            "latency_ms": self.latency_ms,
            "truncated": self.truncated,
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class HFSummarizationService:
    """
    Reusable wrapper around a HuggingFace seq2seq summarisation pipeline.

    Usage (singleton pattern – see get_default_service()):
        service = HFSummarizationService()
        output  = service.summarize("Long article text …")

    Or inject a custom model for testing / experimentation:
        service = HFSummarizationService(model_name="facebook/bart-large-cnn")
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: int = -1,                       # -1 = CPU; 0 = first GPU
        max_input_tokens: int = 1024,           # clip inputs longer than this
        max_new_tokens: int = _MAX_NEW_TOKENS_DEFAULT,
        min_new_tokens: int = _MIN_NEW_TOKENS,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._max_input_tokens = max_input_tokens
        self._max_new_tokens = max_new_tokens
        self._min_new_tokens = min_new_tokens

        self._pipeline: Any | None = None          # lazy-loaded
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def summarize(
        self,
        text: str,
        max_new_tokens: int | None = None,
        min_new_tokens: int | None = None,
    ) -> SummarizationOutput:
        """
        Generate an abstractive summary of *text*.

        Args:
            text:           Source document (plain text).
            max_new_tokens: Override the service default for this call only.
            min_new_tokens: Override the service default for this call only.

        Returns:
            SummarizationOutput with the summary and execution metadata.

        Raises:
            SummarizationError: Wraps any pipeline / tokenizer failure with
                                a descriptive message.
        """
        if not text or not text.strip():
            raise ValueError("Input text must be a non-empty string.")

        pipeline = self._get_pipeline()

        clipped_text, truncated = self._maybe_clip(text, pipeline)
        effective_max = max_new_tokens or self._max_new_tokens
        effective_min = min_new_tokens or self._min_new_tokens

        t0 = time.perf_counter()
        try:
            raw_output = pipeline(
                clipped_text,
                max_new_tokens=effective_max,
                min_new_tokens=effective_min,
                do_sample=False,        # deterministic / reproducible
                truncation=True,
            )
        except Exception as exc:
            raise SummarizationError(
                f"HuggingFace pipeline failed for model '{self._model_name}': {exc}"
            ) from exc

        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        summary: str = raw_output[0]["summary_text"].strip()
        original_wc = len(text.split())
        summary_wc = len(summary.split())
        ratio = round(original_wc / summary_wc, 2) if summary_wc else 0.0

        logger.debug(
            "Summarization done | model=%s latency=%.1fms words=%d→%d ratio=%.1fx",
            self._model_name, latency_ms, original_wc, summary_wc, ratio,
        )

        return SummarizationOutput(
            summary=summary,
            original_word_count=original_wc,
            summary_word_count=summary_wc,
            compression_ratio=ratio,
            model_name=self._model_name,
            latency_ms=latency_ms,
            truncated=truncated,
        )

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def is_loaded(self) -> bool:
        """True once the pipeline has been initialised."""
        return self._pipeline is not None

    def warmup(self) -> None:
        """
        Pre-load the model eagerly (e.g. call at application startup to
        avoid a slow first request).
        """
        self._get_pipeline()
        logger.info("Summarization model warmed up: %s", self._model_name)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_pipeline(self) -> Any:
        """Return the cached pipeline, building it on first call (thread-safe)."""
        if self._pipeline is not None:
            return self._pipeline

        with self._lock:
            # Double-checked locking: another thread may have built it while
            # we were waiting for the lock.
            if self._pipeline is None:
                self._pipeline = self._build_pipeline()

        return self._pipeline

    def _build_pipeline(self) -> Any:
        """
        Construct the HuggingFace pipeline.

        Separated into its own method so unit tests can mock just this step
        without patching the entire transformers library.
        """
        try:
            from transformers import pipeline as hf_pipeline  # type: ignore[import]
        except ImportError as exc:
            raise SummarizationError(
                "The 'transformers' package is not installed. "
                "Run: pip install transformers torch"
            ) from exc

        logger.info(
            "Loading summarization model '%s' on device=%s …",
            self._model_name,
            "CPU" if self._device == -1 else f"GPU:{self._device}",
        )
        t0 = time.perf_counter()
        pipe = hf_pipeline(
            task="summarization",
            model=self._model_name,
            device=self._device,
        )
        elapsed = round((time.perf_counter() - t0) * 1000)
        logger.info("Model loaded in %d ms.", elapsed)
        return pipe

    def _maybe_clip(self, text: str, pipeline: Any) -> tuple[str, bool]:
        """
        Clip *text* to at most `max_input_tokens` tokens using the pipeline's
        tokenizer so the model never sees an oversized input.

        Returns (clipped_text, was_truncated).
        """
        try:
            tokenizer = pipeline.tokenizer
            tokens = tokenizer.encode(text, add_special_tokens=False)
            if len(tokens) <= self._max_input_tokens:
                return text, False
            clipped_tokens = tokens[: self._max_input_tokens]
            clipped_text = tokenizer.decode(clipped_tokens, skip_special_tokens=True)
            logger.warning(
                "Input truncated from %d to %d tokens for model '%s'.",
                len(tokens), self._max_input_tokens, self._model_name,
            )
            return clipped_text, True
        except Exception:  # noqa: BLE001
            # If tokenizer access fails, pass the raw text and let the
            # pipeline's own truncation handle it.
            return text, False


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class SummarizationError(RuntimeError):
    """Raised when the summarisation service encounters an unrecoverable error."""


# ---------------------------------------------------------------------------
# Module-level singleton (optional convenience)
# ---------------------------------------------------------------------------

_default_service: HFSummarizationService | None = None
_singleton_lock = threading.Lock()


def get_default_service(model_name: str = DEFAULT_MODEL) -> HFSummarizationService:
    """
    Return a process-wide singleton HFSummarizationService.

    Safe to call from multiple threads; the model is loaded exactly once.
    """
    global _default_service
    if _default_service is not None:
        return _default_service
    with _singleton_lock:
        if _default_service is None:
            _default_service = HFSummarizationService(model_name=model_name)
    return _default_service
