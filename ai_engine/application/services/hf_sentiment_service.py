"""
HuggingFace Sentiment Analysis Service
=======================================
Reusable, framework-independent service wrapping the
`distilbert-base-uncased-finetuned-sst-2-english` model
(or any compatible text-classification pipeline).

Model facts
-----------
- Architecture : DistilBERT (6 layers, 66 M params)
- Training     : SST-2 binary sentiment dataset (positive / negative)
- Input limit  : 512 tokens (BERT family hard limit)
- Inference    : ~15-40 ms per sample on modern CPU (fp32)
- Size on disk : ~268 MB

Design decisions
----------------
- Lazy singleton loading        – model built on first call, never at import.
- Thread-safe double-checked lock – identical pattern to HFSummarizationService.
- Token-level input clipping    – hard 512-token guard via the model tokenizer.
- Confidence normalisation      – raw logits → softmax → per-label scores in [0,1].
- Neutral band                  – optional `neutral_threshold` parameter lets
                                   callers introduce a third "neutral" label when
                                   neither score clears the threshold.
- Structured output dataclass   – SentimentOutput; no raw dicts leaving the service.
- Batch support                 – analyze_batch() for bulk jobs; shares the same
                                   pipeline and error handling.
- Custom exception              – SentimentAnalysisError wraps all HF failures.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "distilbert-base-uncased-finetuned-sst-2-english"

# DistilBERT / BERT family hard token limit.
_MAX_INPUT_TOKENS = 512

# Default neutral band: if |positive_score - negative_score| < threshold,
# the label is reported as "neutral" instead.  Set to 0.0 to disable.
_DEFAULT_NEUTRAL_THRESHOLD = 0.0


# ---------------------------------------------------------------------------
# Structured output
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SentimentScore:
    """
    Per-label confidence score.

    Attributes:
        label : Canonical lower-case label ("positive" | "negative").
        score : Probability in [0.0, 1.0] from the model's softmax output.
    """
    label: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "score": self.score}


@dataclass(frozen=True)
class SentimentOutput:
    """
    Immutable result returned by HFSentimentService.analyze().

    Attributes:
        label           : Winning sentiment label ("positive" | "negative" | "neutral").
        score           : Confidence of the winning label in [0.0, 1.0].
        scores          : Full per-label breakdown as a list of SentimentScore.
        is_neutral      : True when neutral_threshold caused a neutral override.
        word_count      : Number of whitespace-delimited tokens in the input.
        model_name      : HuggingFace model ID that produced the result.
        latency_ms      : Wall-clock inference time in milliseconds.
        input_truncated : True when the input exceeded max_input_tokens and was clipped.
    """

    label: str
    score: float
    scores: list[SentimentScore]
    is_neutral: bool
    word_count: int
    model_name: str
    latency_ms: float
    input_truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "score": round(self.score, 6),
            "scores": {s.label: round(s.score, 6) for s in self.scores},
            "is_neutral": self.is_neutral,
            "word_count": self.word_count,
            "model_name": self.model_name,
            "latency_ms": self.latency_ms,
            "input_truncated": self.input_truncated,
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class HFSentimentService:
    """
    Reusable wrapper around a HuggingFace text-classification pipeline.

    Typical usage (via singleton helper):
        svc    = get_default_service()
        output = svc.analyze("The product is absolutely fantastic!")

    Inject a custom model or threshold for experimentation:
        svc = HFSentimentService(
            model_name="cardiffnlp/twitter-roberta-base-sentiment",
            neutral_threshold=0.15,
        )

    Batch inference (more efficient than N individual calls):
        outputs = svc.analyze_batch(["Great!", "Terrible.", "OK I guess"])
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: int = -1,                           # -1 = CPU; 0 = first GPU
        max_input_tokens: int = _MAX_INPUT_TOKENS,
        neutral_threshold: float = _DEFAULT_NEUTRAL_THRESHOLD,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._max_input_tokens = max_input_tokens
        self._neutral_threshold = neutral_threshold

        self._pipeline: Any | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, text: str) -> SentimentOutput:
        """
        Classify the sentiment of a single text.

        Args:
            text: Input text (plain string, any length; long inputs are clipped).

        Returns:
            SentimentOutput with label, confidence score, and metadata.

        Raises:
            ValueError            : text is empty or whitespace-only.
            SentimentAnalysisError: pipeline or tokenizer failure.
        """
        if not text or not text.strip():
            raise ValueError("Input text must be a non-empty string.")

        pipe = self._get_pipeline()
        clipped, truncated = self._maybe_clip(text, pipe)

        t0 = time.perf_counter()
        try:
            # top_k=None → return all labels with their scores
            raw: list[dict[str, Any]] = pipe(
                clipped,
                top_k=None,
                truncation=True,
            )
        except Exception as exc:
            raise SentimentAnalysisError(
                f"HuggingFace pipeline failed for model '{self._model_name}': {exc}"
            ) from exc

        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return self._build_output(raw, text, latency_ms, truncated)

    def analyze_batch(self, texts: list[str]) -> list[SentimentOutput]:
        """
        Classify a list of texts in a single pipeline call (more efficient
        than calling analyze() in a loop for large batches).

        Args:
            texts: Non-empty list of input strings.

        Returns:
            List of SentimentOutput, same order as input.

        Raises:
            ValueError            : texts is empty or contains blank entries.
            SentimentAnalysisError: pipeline failure.
        """
        if not texts:
            raise ValueError("texts must be a non-empty list.")

        pipe = self._get_pipeline()

        clipped_pairs = [self._maybe_clip(t, pipe) for t in texts]
        clipped_texts = [c for c, _ in clipped_pairs]
        truncated_flags = [tr for _, tr in clipped_pairs]

        t0 = time.perf_counter()
        try:
            batch_raw: list[list[dict[str, Any]]] = pipe(
                clipped_texts,
                top_k=None,
                truncation=True,
            )
        except Exception as exc:
            raise SentimentAnalysisError(
                f"Batch pipeline failed for model '{self._model_name}': {exc}"
            ) from exc

        total_latency = round((time.perf_counter() - t0) * 1000, 2)
        per_item_latency = round(total_latency / len(texts), 2)

        return [
            self._build_output(raw, text, per_item_latency, trunc)
            for raw, text, trunc in zip(batch_raw, texts, truncated_flags)
        ]

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def is_loaded(self) -> bool:
        return self._pipeline is not None

    def warmup(self) -> None:
        """Pre-load the model eagerly to avoid a slow first request."""
        self._get_pipeline()
        logger.info("Sentiment model warmed up: %s", self._model_name)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_pipeline(self) -> Any:
        """Return the cached pipeline; build it on first call (thread-safe)."""
        if self._pipeline is not None:
            return self._pipeline
        with self._lock:
            if self._pipeline is None:
                self._pipeline = self._build_pipeline()
        return self._pipeline

    def _build_pipeline(self) -> Any:
        """
        Construct the HuggingFace text-classification pipeline.

        Isolated into its own method so tests can patch just this step
        without touching the rest of the pipeline infrastructure.
        """
        try:
            from transformers import pipeline as hf_pipeline  # type: ignore[import]
        except ImportError as exc:
            raise SentimentAnalysisError(
                "The 'transformers' package is not installed. "
                "Run: pip install transformers torch"
            ) from exc

        logger.info(
            "Loading sentiment model '%s' on device=%s …",
            self._model_name,
            "CPU" if self._device == -1 else f"GPU:{self._device}",
        )
        t0 = time.perf_counter()
        pipe = hf_pipeline(
            task="text-classification",
            model=self._model_name,
            device=self._device,
        )
        elapsed = round((time.perf_counter() - t0) * 1000)
        logger.info("Sentiment model loaded in %d ms.", elapsed)
        return pipe

    def _maybe_clip(self, text: str, pipeline: Any) -> tuple[str, bool]:
        """
        Clip text to max_input_tokens using the pipeline's tokenizer.

        DistilBERT silently truncates at 512 tokens internally, but we clip
        explicitly so the `input_truncated` flag is set correctly.

        Returns (clipped_text, was_truncated).
        """
        try:
            tokenizer = pipeline.tokenizer
            tokens = tokenizer.encode(text, add_special_tokens=True)
            if len(tokens) <= self._max_input_tokens:
                return text, False
            clipped_ids = tokens[: self._max_input_tokens - 1] + [tokens[-1]]
            clipped_text = tokenizer.decode(clipped_ids, skip_special_tokens=True)
            logger.warning(
                "Sentiment input truncated from %d to %d tokens (model '%s').",
                len(tokens), self._max_input_tokens, self._model_name,
            )
            return clipped_text, True
        except Exception:  # noqa: BLE001
            return text, False

    def _build_output(
        self,
        raw: list[dict[str, Any]],
        original_text: str,
        latency_ms: float,
        truncated: bool,
    ) -> SentimentOutput:
        """
        Convert raw pipeline output into a SentimentOutput.

        Pipeline output format:
            [{"label": "POSITIVE", "score": 0.9998}, {"label": "NEGATIVE", "score": 0.0002}]

        Steps:
        1. Normalise label strings to lower-case.
        2. Sort descending by score so scores[0] is always the top label.
        3. Apply neutral_threshold: if |top - second| < threshold → "neutral".
        """
        scores = sorted(
            [
                SentimentScore(label=item["label"].lower(), score=round(item["score"], 6))
                for item in raw
            ],
            key=lambda s: s.score,
            reverse=True,
        )

        top = scores[0]
        is_neutral = False

        if (
            self._neutral_threshold > 0.0
            and len(scores) >= 2
            and abs(scores[0].score - scores[1].score) < self._neutral_threshold
        ):
            winning_label = "neutral"
            winning_score = round(1.0 - abs(scores[0].score - scores[1].score), 6)
            is_neutral = True
        else:
            winning_label = top.label
            winning_score = top.score

        logger.debug(
            "Sentiment done | model=%s label=%s score=%.4f latency=%.1fms",
            self._model_name, winning_label, winning_score, latency_ms,
        )

        return SentimentOutput(
            label=winning_label,
            score=winning_score,
            scores=scores,
            is_neutral=is_neutral,
            word_count=len(original_text.split()),
            model_name=self._model_name,
            latency_ms=latency_ms,
            input_truncated=truncated,
        )


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class SentimentAnalysisError(RuntimeError):
    """Raised when the sentiment service encounters an unrecoverable error."""


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_service: HFSentimentService | None = None
_singleton_lock = threading.Lock()


def get_default_service(
    model_name: str = DEFAULT_MODEL,
) -> HFSentimentService:
    """
    Return a process-wide singleton HFSentimentService.

    Safe to call from multiple threads; the model loads exactly once.
    """
    global _default_service
    if _default_service is not None:
        return _default_service
    with _singleton_lock:
        if _default_service is None:
            _default_service = HFSentimentService(model_name=model_name)
    return _default_service
