"""
Integration tests for the Flask REST interface.

Uses pytest + Flask test client.
Injects an in-memory repository so no real MongoDB is needed.
"""

from __future__ import annotations

import pytest

from ai_engine.application.orchestrator import AIJobOrchestrator
from ai_engine.application.tasks.dataset_profiling import DatasetProfilingTask
from ai_engine.application.tasks.sentiment_analysis import SentimentAnalysisTask
from ai_engine.application.tasks.summarization import SummarizationTask
from ai_engine.domain.models import AIJobStatus, AIJobType
from ai_engine.domain.repositories import AIJobRepository
from ai_engine.infrastructure.workers.job_worker import AIJobWorker
from ai_engine.interfaces.flask_routes import ai_bp
from flask import Flask

# Reuse in-memory repo from unit tests
from tests.unit.test_orchestrator import InMemoryRepository


# ---------------------------------------------------------------------------
# Test app factory
# ---------------------------------------------------------------------------

def create_test_app() -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True

    repo = InMemoryRepository()
    registry = {
        AIJobType.SUMMARIZATION: SummarizationTask(),
        AIJobType.SENTIMENT_ANALYSIS: SentimentAnalysisTask(),
        AIJobType.DATASET_PROFILING: DatasetProfilingTask(),
    }
    orchestrator = AIJobOrchestrator(repository=repo, task_registry=registry)
    # Use 1 worker thread for deterministic test behaviour
    worker = AIJobWorker(orchestrator=orchestrator, max_workers=1)

    app.extensions["ai_engine_worker"] = worker
    app.register_blueprint(ai_bp)
    return app


@pytest.fixture
def client():
    app = create_test_app()
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSubmitJob:
    def test_returns_202_with_job_id(self, client):
        resp = client.post(
            "/api/ai/jobs",
            json={"job_type": "summarization", "payload": {"text": "hello world"}},
        )
        assert resp.status_code == 202
        data = resp.get_json()
        assert "job_id" in data
        assert data["status"] == "pending"

    def test_missing_job_type_returns_400(self, client):
        resp = client.post("/api/ai/jobs", json={"payload": {}})
        assert resp.status_code == 400

    def test_invalid_job_type_returns_400(self, client):
        resp = client.post("/api/ai/jobs", json={"job_type": "magic_ai"})
        assert resp.status_code == 400


class TestGetJob:
    def test_get_existing_job(self, client):
        post = client.post(
            "/api/ai/jobs",
            json={"job_type": "sentiment_analysis", "payload": {"text": "great product"}},
        )
        job_id = post.get_json()["job_id"]

        # Give the worker a moment (it runs in background thread)
        import time; time.sleep(0.3)

        get = client.get(f"/api/ai/jobs/{job_id}")
        assert get.status_code == 200
        body = get.get_json()
        assert body["job_id"] == job_id

    def test_get_nonexistent_job_returns_404(self, client):
        resp = client.get("/api/ai/jobs/does-not-exist")
        assert resp.status_code == 404
