"""HTTP probe application for ai-worker."""

from datetime import datetime, timezone

from flask import Flask, current_app, jsonify

from shared.shared_logging import register_flask_request_logging

from ..config import Config, get_config
from ..container import ServiceContainer, init_container
from ..infrastructure.capabilities.system_detector import SystemCapabilityDetector
from ..infrastructure.jobs.job_manager import JobManager
from ..infrastructure.messaging.celery_app import create_celery_app
from ..infrastructure.workloads.placeholder_runner import PlaceholderWorkloadRunner
from ..logger import get_logger, setup_logging
from .routes.jobs import create_jobs_blueprint

logger = get_logger(__name__)


def create_app(config: Config = None, container: ServiceContainer = None) -> Flask:
    """Create the HTTP health/status app for the Celery worker service."""

    if config is None:
        config = get_config()
    if container is None:
        container = ServiceContainer()

    setup_logging(config.LOG_LEVEL, config.LOG_FORMAT)
    container.register_instance("config", config)
    _register_worker_infrastructure(container, config)
    init_container(container)

    app = Flask(__name__)
    app.config.from_object(config)
    register_flask_request_logging(app, service_name=config.SERVICE_NAME)
    _register_routes(app, container)

    logger.info(
        "Created ai-worker probe app",
        extra={"environment": config.FLASK_ENV, "queue": config.CELERY_TASK_DEFAULT_QUEUE},
    )
    return app


def _register_worker_infrastructure(container: ServiceContainer, config: Config) -> None:
    container.register_instance("celery_app", create_celery_app(config))
    container.register("capability_detector", SystemCapabilityDetector, singleton=True)
    container.register("workload_runner", PlaceholderWorkloadRunner, singleton=True)
    
    # Register job manager for async job tracking
    container.register("job_manager", lambda: JobManager(), singleton=True)
    


def _register_routes(app: Flask, container: ServiceContainer) -> None:
    @app.route("/health", methods=["GET"])
    @app.route("/api/v1/ai/health", methods=["GET"])
    def health():
        return jsonify(_payload("healthy")), 200

    @app.route("/health/live", methods=["GET"])
    @app.route("/api/v1/ai/health/live", methods=["GET"])
    def liveness():
        return jsonify(_payload("alive")), 200

    @app.route("/health/ready", methods=["GET"])
    @app.route("/api/v1/ai/health/ready", methods=["GET"])
    def readiness():
        broker_ok = _broker_is_available(container.resolve("celery_app"))
        code = 200 if broker_ok else 503
        status = "ready" if broker_ok else "unavailable"
        return jsonify(_payload(status, broker="ok" if broker_ok else "unreachable")), code

    @app.route("/api/v1/ai/capabilities", methods=["GET"])
    def capabilities():
        detector = container.resolve("capability_detector")
        return jsonify(_payload("ok", capabilities=detector.detect().to_dict())), 200
    
    # Register jobs blueprint for async job submission and polling
    jobs_bp = create_jobs_blueprint(container)
    app.register_blueprint(jobs_bp)


def _payload(status: str, **extra) -> dict:
    payload = {
        "status": status,
        "service": current_app.config.get("SERVICE_NAME", "ai_worker"),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
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
