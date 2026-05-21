"""HTTP health app for notification-service."""

from datetime import datetime

from flask import Flask, current_app, jsonify

from shared.shared_logging import register_flask_request_logging

from ..application.use_cases.consume_event import ConsumeEventUseCase
from ..config import Config, get_config
from ..container import ServiceContainer, init_container
from ..infrastructure.messaging.celery_app import create_celery_app
from ..infrastructure.notifications.log_channel import LogNotificationChannel
from ..logger import get_logger, setup_logging

logger = get_logger(__name__)


def create_app(config: Config = None, container: ServiceContainer = None) -> Flask:
    """Create the HTTP probe app for notification-service."""

    if config is None:
        config = get_config()
    if container is None:
        container = ServiceContainer()

    setup_logging(config.LOG_LEVEL, config.LOG_FORMAT)
    container.register_instance("config", config)
    _register_notification_infrastructure(container, config)
    init_container(container)

    app = Flask(__name__)
    app.config.from_object(config)
    register_flask_request_logging(app, service_name=config.SERVICE_NAME)
    _register_routes(app, container)

    logger.info(
        "Created notification-service probe app",
        extra={"environment": config.FLASK_ENV, "queue": config.CELERY_TASK_DEFAULT_QUEUE},
    )
    return app


def _register_notification_infrastructure(container: ServiceContainer, config: Config) -> None:
    container.register_instance("celery_app", create_celery_app(config))
    container.register("notification_channel", LogNotificationChannel, singleton=True)
    container.register(
        "event_consumer",
        lambda: ConsumeEventUseCase(channel=container.resolve("notification_channel")),
        singleton=True,
    )


def _register_routes(app: Flask, container: ServiceContainer) -> None:
    @app.route("/health", methods=["GET"])
    @app.route("/api/v1/notifications/health", methods=["GET"])
    def health():
        return jsonify(_payload("healthy")), 200

    @app.route("/health/live", methods=["GET"])
    @app.route("/api/v1/notifications/health/live", methods=["GET"])
    def liveness():
        return jsonify(_payload("alive")), 200

    @app.route("/health/ready", methods=["GET"])
    @app.route("/api/v1/notifications/health/ready", methods=["GET"])
    def readiness():
        broker_ok = _broker_is_available(container.resolve("celery_app"))
        return jsonify(_payload(
            "ready" if broker_ok else "unavailable",
            broker="ok" if broker_ok else "unreachable",
        )), 200 if broker_ok else 503

    @app.route("/api/v1/notifications/channels", methods=["GET"])
    def channels():
        configured = [container.resolve("notification_channel").name]
        future = ["email", "webhook"]
        return jsonify(_payload("ok", channels=configured, future_channels=future)), 200


def _payload(status: str, **extra) -> dict:
    payload = {
        "status": status,
        "service": current_app.config.get("SERVICE_NAME", "notification_service"),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    payload.update(extra)
    return payload


def _broker_is_available(celery_app) -> bool:
    try:
        conn = celery_app.connection(transport_options={"max_retries": 1})
        conn.ensure_connection(max_retries=1)
        conn.close()
        return True
    except Exception:
        return False
