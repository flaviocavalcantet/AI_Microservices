"""Unit tests for individual AI tasks (no I/O, no DB)."""

import pytest

from ai_engine.application.tasks.dataset_profiling import DatasetProfilingTask
from ai_engine.application.tasks.sentiment_analysis import SentimentAnalysisTask
from ai_engine.application.tasks.summarization import SummarizationTask


class TestSummarizationTask:
    def setup_method(self):
        self.task = SummarizationTask()

    def test_returns_success(self):
        result = self.task.execute({"text": "Sentence one. Sentence two. Sentence three."})
        assert result.success is True
        assert "summary" in result.data

    def test_respects_max_sentences(self):
        text = "A. B. C. D. E."
        result = self.task.execute({"text": text, "max_sentences": 2})
        assert result.success is True
        # Only 2 sentences in summary
        parts = result.data["summary"].split(". ")
        assert len(parts) <= 2

    def test_validate_empty_text_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            self.task.validate_payload({"text": "   "})

    def test_injected_summariser_used(self):
        custom = lambda text, n: "CUSTOM"  # noqa: E731
        task = SummarizationTask(summariser=custom)
        result = task.execute({"text": "anything"})
        assert result.data["summary"] == "CUSTOM"

    def test_summariser_exception_returns_failure(self):
        def bad(_t, _n):
            raise RuntimeError("model crash")

        task = SummarizationTask(summariser=bad)
        result = task.execute({"text": "hello"})
        assert result.success is False
        assert "model crash" in result.error


class TestSentimentAnalysisTask:
    def setup_method(self):
        self.task = SentimentAnalysisTask()

    def test_positive_text(self):
        result = self.task.execute({"text": "This is great and wonderful!"})
        assert result.success is True
        assert result.data["label"] == "positive"

    def test_negative_text(self):
        result = self.task.execute({"text": "This is terrible and horrible."})
        assert result.success is True
        assert result.data["label"] == "negative"

    def test_validate_empty_text_raises(self):
        with pytest.raises(ValueError):
            self.task.validate_payload({"text": ""})

    def test_score_between_0_and_1(self):
        result = self.task.execute({"text": "OK product"})
        assert 0.0 <= result.data["score"] <= 1.0

    def test_analyser_exception_returns_failure(self):
        def bad(_t):
            raise ValueError("analyser down")

        task = SentimentAnalysisTask(analyser=bad)
        result = task.execute({"text": "hello"})
        assert result.success is False


class TestDatasetProfilingTask:
    def setup_method(self):
        self.task = DatasetProfilingTask()
        self.sample_data = [
            {"name": "Alice", "age": 30, "score": 9.5},
            {"name": "Bob", "age": None, "score": 7.0},
            {"name": "Carol", "age": 25, "score": 8.0},
        ]

    def test_returns_success(self):
        result = self.task.execute({"data": self.sample_data})
        assert result.success is True

    def test_row_and_column_count(self):
        result = self.task.execute({"data": self.sample_data})
        assert result.data["row_count"] == 3
        assert result.data["column_count"] == 3

    def test_numeric_column_stats(self):
        result = self.task.execute({"data": self.sample_data})
        score_col = result.data["columns"]["score"]
        assert score_col["type"] == "numeric"
        assert score_col["min"] == 7.0
        assert score_col["max"] == 9.5

    def test_null_count(self):
        result = self.task.execute({"data": self.sample_data})
        assert result.data["columns"]["age"]["null_count"] == 1

    def test_validate_missing_data_key(self):
        with pytest.raises(ValueError, match="'data' key"):
            self.task.validate_payload({})

    def test_validate_empty_list(self):
        with pytest.raises(ValueError, match="at least one"):
            self.task.validate_payload({"data": []})
