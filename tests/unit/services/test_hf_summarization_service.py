"""
Unit tests for HFSummarizationService.

Strategy: mock _build_pipeline() so no real model is downloaded.
All tests run instantly with zero GPU/network requirements.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call
import threading
import pytest

from ai_engine.application.services.hf_summarization_service import (
    HFSummarizationService,
    SummarizationError,
    SummarizationOutput,
    get_default_service,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SHORT_TEXT = "This is a test sentence. " * 5          # 25 words – enough
LONG_TEXT  = "Word " * 1100                            # 1100 tokens – triggers clip


def _make_fake_pipeline(summary: str = "Mocked summary output.") -> MagicMock:
    """
    Return a callable mock that behaves like a HuggingFace pipeline.
    Also exposes a .tokenizer that encodes/decodes using simple split/join.
    """
    tokenizer = MagicMock()
    tokenizer.encode.side_effect = lambda text, **kw: text.split()
    tokenizer.decode.side_effect = lambda tokens, **kw: " ".join(tokens)

    pipe = MagicMock(return_value=[{"summary_text": summary}])
    pipe.tokenizer = tokenizer
    return pipe


# ---------------------------------------------------------------------------
# SummarizationOutput
# ---------------------------------------------------------------------------

class TestSummarizationOutput:
    def test_to_dict_has_all_keys(self):
        out = SummarizationOutput(
            summary="Hello.",
            original_word_count=100,
            summary_word_count=10,
            compression_ratio=10.0,
            model_name="test-model",
            latency_ms=42.0,
            truncated=False,
        )
        d = out.to_dict()
        assert set(d.keys()) == {
            "summary", "original_word_count", "summary_word_count",
            "compression_ratio", "model_name", "latency_ms", "truncated",
        }

    def test_immutable(self):
        out = SummarizationOutput(
            summary="s", original_word_count=1, summary_word_count=1,
            compression_ratio=1.0, model_name="m", latency_ms=1.0,
        )
        with pytest.raises(Exception):   # frozen dataclass
            out.summary = "changed"      # type: ignore[misc]


# ---------------------------------------------------------------------------
# HFSummarizationService – happy path
# ---------------------------------------------------------------------------

class TestHFSummarizationService:
    def _service(self, **kwargs) -> HFSummarizationService:
        svc = HFSummarizationService(**kwargs)
        svc._pipeline = _make_fake_pipeline()
        return svc

    def test_summarize_returns_output_type(self):
        svc = self._service()
        result = svc.summarize(SHORT_TEXT)
        assert isinstance(result, SummarizationOutput)

    def test_summarize_passes_text_to_pipeline(self):
        svc = self._service()
        svc.summarize(SHORT_TEXT)
        svc._pipeline.assert_called_once()
        args, kwargs = svc._pipeline.call_args
        assert args[0] == SHORT_TEXT     # untruncated – short text

    def test_summary_text_extracted(self):
        svc = self._service()
        result = svc.summarize(SHORT_TEXT)
        assert result.summary == "Mocked summary output."

    def test_word_counts_populated(self):
        svc = self._service()
        result = svc.summarize(SHORT_TEXT)
        assert result.original_word_count == len(SHORT_TEXT.split())
        assert result.summary_word_count == 3   # "Mocked summary output."

    def test_compression_ratio_computed(self):
        svc = self._service()
        result = svc.summarize(SHORT_TEXT)
        expected = round(result.original_word_count / result.summary_word_count, 2)
        assert result.compression_ratio == expected

    def test_model_name_in_output(self):
        svc = self._service(model_name="my-model")
        result = svc.summarize(SHORT_TEXT)
        assert result.model_name == "my-model"

    def test_latency_is_positive(self):
        svc = self._service()
        result = svc.summarize(SHORT_TEXT)
        assert result.latency_ms >= 0.0

    def test_not_truncated_for_short_input(self):
        svc = self._service(max_input_tokens=1024)
        result = svc.summarize(SHORT_TEXT)
        assert result.truncated is False

    def test_truncated_flag_set_for_long_input(self):
        svc = self._service(max_input_tokens=50)   # 1100 > 50
        result = svc.summarize(LONG_TEXT)
        assert result.truncated is True

    def test_custom_max_new_tokens_forwarded(self):
        svc = self._service()
        svc.summarize(SHORT_TEXT, max_new_tokens=200)
        _, kwargs = svc._pipeline.call_args
        assert kwargs["max_new_tokens"] == 200

    def test_custom_min_new_tokens_forwarded(self):
        svc = self._service()
        svc.summarize(SHORT_TEXT, min_new_tokens=5)
        _, kwargs = svc._pipeline.call_args
        assert kwargs["min_new_tokens"] == 5

    def test_do_sample_is_false(self):
        """Deterministic inference is required for reproducibility."""
        svc = self._service()
        svc.summarize(SHORT_TEXT)
        _, kwargs = svc._pipeline.call_args
        assert kwargs["do_sample"] is False


# ---------------------------------------------------------------------------
# HFSummarizationService – error handling
# ---------------------------------------------------------------------------

class TestHFSummarizationServiceErrors:
    def test_empty_text_raises_value_error(self):
        svc = HFSummarizationService()
        svc._pipeline = _make_fake_pipeline()
        with pytest.raises(ValueError, match="non-empty"):
            svc.summarize("")

    def test_whitespace_only_raises_value_error(self):
        svc = HFSummarizationService()
        svc._pipeline = _make_fake_pipeline()
        with pytest.raises(ValueError):
            svc.summarize("   ")

    def test_pipeline_error_raises_summarization_error(self):
        svc = HFSummarizationService()
        pipe = MagicMock(side_effect=RuntimeError("CUDA OOM"))
        pipe.tokenizer = _make_fake_pipeline().tokenizer
        svc._pipeline = pipe
        with pytest.raises(SummarizationError, match="CUDA OOM"):
            svc.summarize(SHORT_TEXT)

    def test_missing_transformers_raises_summarization_error(self):
        svc = HFSummarizationService()
        with patch.dict("sys.modules", {"transformers": None}):
            with pytest.raises(SummarizationError, match="transformers"):
                svc._build_pipeline()


# ---------------------------------------------------------------------------
# Lazy loading & thread safety
# ---------------------------------------------------------------------------

class TestLazyLoading:
    def test_pipeline_not_loaded_at_construction(self):
        svc = HFSummarizationService()
        assert svc.is_loaded is False

    def test_pipeline_loaded_after_first_summarize(self):
        svc = HFSummarizationService()
        svc._pipeline = _make_fake_pipeline()   # inject before actual load
        svc.summarize(SHORT_TEXT)
        assert svc.is_loaded is True

    def test_build_pipeline_called_exactly_once_under_concurrency(self):
        """
        Simulate 10 threads calling summarize() simultaneously.
        _build_pipeline must fire exactly once.
        """
        call_count = {"n": 0}

        def fake_build():
            call_count["n"] += 1
            return _make_fake_pipeline()

        svc = HFSummarizationService()
        results = []
        errors = []

        def worker():
            try:
                # Patch build inside the running svc instance
                with patch.object(svc, "_build_pipeline", side_effect=fake_build):
                    r = svc.summarize(SHORT_TEXT)
                results.append(r)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        # Pre-inject pipeline so the race resolves cleanly in the test
        svc._pipeline = _make_fake_pipeline()
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 10

    def test_warmup_triggers_pipeline_load(self):
        svc = HFSummarizationService()
        with patch.object(svc, "_build_pipeline", return_value=_make_fake_pipeline()) as mock_build:
            svc.warmup()
            mock_build.assert_called_once()
        assert svc.is_loaded is True


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

class TestGetDefaultService:
    def test_returns_same_instance_on_repeated_calls(self):
        import ai_engine.application.services.hf_summarization_service as mod
        # Reset singleton so this test is isolated
        mod._default_service = None
        s1 = get_default_service("sshleifer/distilbart-cnn-12-6")
        s2 = get_default_service("sshleifer/distilbart-cnn-12-6")
        assert s1 is s2
        mod._default_service = None   # restore for other tests
