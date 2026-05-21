"""Tests for notification-service base structure."""

import json
import logging

import pytest

from services.notification_service.src.application.ports.event_consumer import EventConsumer
from services.notification_service.src.application.ports.notification_channel import NotificationChannel
from services.notification_service.src.config import get_config
from services.notification_service.src.container import ServiceContainer, get_container
from services.notification_service.src.domain.value_objects.event import EventEnvelope
from services.notification_service.src.infrastructure.messaging.celery_app import create_celery_app
from services.notification_service.src.infrastructure.notifications.email_channel import EmailNotificationChannel
from services.notification_service.src.infrastructure.notifications.webhook_channel import WebhookNotificationChannel
from services.notification_service.src.infrastructure.tasks.events import consume_event
from services.notification_service.src.logger import JSONFormatter
from services.notification_service.src.presentation.app import create_app


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")
    return create_app(config=get_config("testing"))


def test_health_and_channel_endpoints_are_available(app):
    client = app.test_client()

    assert client.get("/health").status_code == 200
    assert client.get("/health/live").status_code == 200
    assert client.get("/api/v1/notifications/health").status_code == 200

    channels = client.get("/api/v1/notifications/channels")
    assert channels.status_code == 200
    assert channels.get_json()["channels"] == ["log"]
    assert {"email", "webhook"}.issubset(set(channels.get_json()["future_channels"]))


def test_notification_infrastructure_ports_are_registered(app):
    container = get_container()

    assert container.resolve("celery_app").main == "notification_service"
    assert isinstance(container.resolve("notification_channel"), NotificationChannel)
    assert isinstance(container.resolve("event_consumer"), EventConsumer)


def test_consume_event_logs_notification_intent():
    result = consume_event.run({
        "event_id": "evt-123",
        "event_type": "JobCompleted",
        "source": "api_service",
        "payload": {"job_id": "job-123"},
    })

    assert result["status"] == "logged"
    assert result["channel"] == "log"
    assert result["event_type"] == "JobCompleted"


def test_event_envelope_normalizes_missing_fields():
    event = EventEnvelope.from_dict({"payload": {"hello": "world"}})

    assert event.event_type == "unknown"
    assert event.source == "unknown"
    assert event.payload == {"hello": "world"}


def test_future_channels_are_not_implemented_yet():
    with pytest.raises(NotImplementedError):
        EmailNotificationChannel().send(None)
    with pytest.raises(NotImplementedError):
        WebhookNotificationChannel().send(None)


def test_celery_app_is_rabbitmq_ready_and_json_configured():
    config = get_config("development")
    celery_app = create_celery_app(config)

    assert celery_app.conf.broker_url == config.CELERY_BROKER_URL
    assert celery_app.conf.result_backend == config.CELERY_RESULT_BACKEND
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.task_default_queue == "notifications.default"


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
        name="notification-test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.event_type = "JobCompleted"
    record.service = "notification_service"

    payload = json.loads(JSONFormatter().format(record))

    assert payload["event_type"] == "JobCompleted"
    assert payload["service"] == "notification_service"
