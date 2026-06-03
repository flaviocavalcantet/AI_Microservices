"""
Unit tests for SummarizationTask.

All tests use a stub HFSummarizationService – no real model is needed.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from ai_engine.application.tasks.summarization import SummarizationTask, _MIN_WORD_COUNT
from ai_engine.application.services.hf_summarization_service import (
    SummarizationError,
    SummarizationOutput,
)
from ai_engine.domain.models import AIJobResult, AIJobType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_output(**overrides) -> SummarizationOutput:
    defaults = dict(
        summary="A concise summary.",
        original_word_count=200,
        summary_word_count=5,
        compression_ratio=40.0,
        model_name="sshleifer/distilbart-cnn-12-6",
        latency_ms=312.0,
        truncated=False,
    )
    defaults.update(overrides)
    return SummarizationOutput(**defaults)


def _make_service(output: SummarizationOutput | None = None, raises=None) -> MagicMock:
    svc = MagicMock()
    if raises:
        svc.summarize.side_effect = raises
    else:
        svc.summarize.return_value = output or _fake_output()
    return svc


def _long_text(words: int = 30) -> str:
    return ("word " * words).strip()


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def task():
    return SummarizationTask(service=_make_service())


# ---------------------------------------------------------------------------
# validate_payload
# ---------------------------------------------------------------------------

class TestSummarizationTaskValidation:
    def test_empty_text_fails(self):
        t = SummarizationTask(service=_make_service())
        with pytest.raises(ValueError, match="non-empty"):
            t.validate_payload({"text": ""})

    def test_whitespace_only_fails(self):
        t = SummarizationTask(service=_make_service())
        with pytest.raises(ValueError):
            t.validate_payload({"text": "   "})

    def test_too_short_fails(self):
        t = SummarizationTask(service=_make_service())
        with pytest.raises(ValueError, match="too short"):
            t.validate_payload({"text": "only three words"})

    def test_minimum_length_passes(self):
        t = SummarizationTask(service=_make_service())
        t.validate_payload({"text": _long_text(_MIN_WORD_COUNT)})  # should not raise

    def test_too_long_fails(self):
        t = SummarizationTask(service=_make_service())
        with pytest.raises(ValueError, match="exceeds maximum"):
            t.validate_payload({"text": "word " * 60_000})

    def test_invalid_max_new_tokens_fails(self):
        t = SummarizationTask(service=_make_service())
        with pytest.raises(ValueError, match="max_new_tokens"):
            t.validate_payload({"text": _long_text(30), "max_new_tokens": -5})

    def test_invalid_min_new_tokens_fails(self):
        t = SummarizationTask(service=_make_service())
        with pytest.raises(ValueError, match="min_new_tokens"):
            t.validate_payload({"text": _long_text(30), "min_new_tokens": 0})

    def test_valid_optional_params_pass(self):
        t = SummarizationTask(service=_make_service())
        t.validate_payload({
            "text": _long_text(30),
            "max_new_tokens": 200,
            "min_new_tokens": 20,
        })


# ---------------------------------------------------------------------------
# execute – happy path
# ---------------------------------------------------------------------------

class TestSummarizationTaskExecute:
    def test_returns_aijobresult(self):
        t = SummarizationTask(service=_make_service())
        result = t.execute({"text": _long_text(30)})
        assert isinstance(result, AIJobResult)

    def test_success_true_on_happy_path(self):
        t = SummarizationTask(service=_make_service())
        result = t.execute({"text": _long_text(30)})
        assert result.success is True

    def test_data_contains_summary(self):
        t = SummarizationTask(service=_make_service())
        result = t.execute({"text": _long_text(30)})
        assert "summary" in result.data
        assert result.data["summary"] == "A concise summary."

    def test_data_contains_word_counts(self):
        t = SummarizationTask(service=_make_service())
        result = t.execute({"text": _long_text(30)})
        assert result.data["original_word_count"] == 200
        assert result.data["summary_word_count"] == 5

    def test_data_contains_compression_ratio(self):
        t = SummarizationTask(service=_make_service())
        result = t.execute({"text": _long_text(30)})
        assert result.data["compression_ratio"] == 40.0

    def test_data_contains_truncated_flag(self):
        output = _fake_output(truncated=True)
        t = SummarizationTask(service=_make_service(output=output))
        result = t.execute({"text": _long_text(30)})
        assert result.data["truncated"] is True

    def test_metadata_contains_model_name(self):
        t = SummarizationTask(service=_make_service())
        result = t.execute({"text": _long_text(30)})
        assert result.metadata["model_name"] == "sshleifer/distilbart-cnn-12-6"

    def test_metadata_contains_latency(self):
        t = SummarizationTask(service=_make_service())
        result = t.execute({"text": _long_text(30)})
        assert result.metadata["latency_ms"] == 312.0

    def test_optional_params_forwarded_to_service(self):
        svc = _make_service()
        t = SummarizationTask(service=svc)
        t.execute({"text": _long_text(30), "max_new_tokens": 99, "min_new_tokens": 10})
        svc.summarize.assert_called_once_with(
            text=_long_text(30),
            max_new_tokens=99,
            min_new_tokens=10,
        )

    def test_job_type_is_summarization(self):
        assert SummarizationTask.job_type == AIJobType.SUMMARIZATION


# ---------------------------------------------------------------------------
# execute – error handling
# ---------------------------------------------------------------------------

class TestSummarizationTaskErrors:
    def test_summarization_error_returns_failure(self):
        svc = _make_service(raises=SummarizationError("pipeline crashed"))
        t = SummarizationTask(service=svc)
        result = t.execute({"text": _long_text(30)})
        assert result.success is False
        assert "pipeline crashed" in result.error

    def test_unexpected_exception_returns_failure(self):
        svc = _make_service(raises=RuntimeError("OOM"))
        t = SummarizationTask(service=svc)
        result = t.execute({"text": _long_text(30)})
        assert result.success is False
        assert "OOM" in result.error

    def test_failure_result_has_no_data(self):
        svc = _make_service(raises=SummarizationError("boom"))
        t = SummarizationTask(service=svc)
        result = t.execute({"text": _long_text(30)})
        assert result.data == {}


# ---------------------------------------------------------------------------
# Lazy service resolution
# ---------------------------------------------------------------------------

class TestSummarizationTaskServiceResolution:
    def test_none_service_resolved_lazily(self):
        """
        When no service is injected, _get_service() must call get_default_service().
        We patch at the module level so no real model is loaded.
        """
        from unittest.mock import patch
        fake_svc = _make_service()
        with patch(
            "ai_engine.application.tasks.summarization.get_default_service",
            return_value=fake_svc,
        ) as mock_factory:
            t = SummarizationTask(service=None)
            t.execute({"text": _long_text(30)})
            mock_factory.assert_called_once()
