"""Tests for ai-worker base structure."""

import json
import logging

import pytest

from services.ai_worker.src.application.ports.capability_detector import CapabilityDetector
from services.ai_worker.src.application.ports.workload_runner import WorkloadRunner
from services.ai_worker.src.config import get_config
from services.ai_worker.src.container import ServiceContainer, get_container
from services.ai_worker.src.infrastructure.messaging.celery_app import create_celery_app
from services.ai_worker.src.logger import JSONFormatter
from services.ai_worker.src.presentation.app import create_app


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")
    return create_app(config=get_config("testing"))


def test_health_and_capability_endpoints_are_available(app):
    client = app.test_client()

    assert client.get("/health").status_code == 200
    assert client.get("/health/live").status_code == 200
    assert client.get("/api/v1/ai/health").status_code == 200

    capabilities = client.get("/api/v1/ai/capabilities")
    assert capabilities.status_code == 200
    assert "gpu" in capabilities.get_json()["capabilities"]
    assert "ram" in capabilities.get_json()["capabilities"]


def test_worker_infrastructure_ports_are_registered(app):
    container = get_container()

    assert container.resolve("celery_app").main == "ai_worker"
    assert isinstance(container.resolve("capability_detector"), CapabilityDetector)
    assert isinstance(container.resolve("workload_runner"), WorkloadRunner)


def test_placeholder_runner_does_not_execute_ai_workloads(app):
    runner = get_container().resolve("workload_runner")

    with pytest.raises(NotImplementedError):
        runner.run({"model": "not-yet"})


def test_celery_app_is_rabbitmq_ready_and_json_configured():
    config = get_config("development")
    celery_app = create_celery_app(config)

    assert celery_app.conf.broker_url == config.CELERY_BROKER_URL
    assert celery_app.conf.result_backend == config.CELERY_RESULT_BACKEND
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.task_default_queue == "ai.default"


def test_testing_config_uses_memory_celery_backend():
    config = get_config("testing")

    assert config.CELERY_BROKER_URL == "memory://"
    assert config.CELERY_RESULT_BACKEND == "cache+memory://"


def test_container_singleton_registration_reuses_instance():
    container = ServiceContainer()
    calls = 0

    def factory():
        nonlocal calls
        calls += 1
        return object()

    container.register("service", factory, singleton=True)

    assert container.resolve("service") is container.resolve("service")
    assert calls == 1


def test_logger_includes_custom_extra_fields():
    record = logging.LogRecord(
        name="ai-worker-test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.queue = "ai.default"
    record.service = "ai_worker"

    payload = json.loads(JSONFormatter().format(record))

    assert payload["queue"] == "ai.default"
    assert payload["service"] == "ai_worker"
