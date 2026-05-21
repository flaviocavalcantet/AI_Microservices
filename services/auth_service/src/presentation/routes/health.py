# Health check endpoints

from datetime import datetime

from flask import Blueprint, current_app, jsonify

health_bp = Blueprint("health", __name__)


def _payload(status: str, **extra):
    payload = {
        "status": status,
        "service": current_app.config.get("SERVICE_NAME", "auth_service"),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    payload.update(extra)
    return payload


@health_bp.route("/health", methods=["GET"])
@health_bp.route("/api/v1/auth/health", methods=["GET"])
def health_check():
    """Basic health probe."""
    return jsonify(_payload("healthy")), 200


@health_bp.route("/health/ready", methods=["GET"])
@health_bp.route("/api/v1/auth/health/ready", methods=["GET"])
def readiness_check():
    """Readiness probe — is the service ready to handle traffic?

    Extend this to check MongoDB and RabbitMQ connectivity
    once those dependencies are wired up.
    """
    dependencies = {
        "database": "not_configured",
        "message_queue": "not_configured",
        "oauth_providers": "not_configured",
    }
    return jsonify(_payload("ready", dependencies=dependencies)), 200


@health_bp.route("/health/live", methods=["GET"])
@health_bp.route("/api/v1/auth/health/live", methods=["GET"])
def liveness_check():
    """Liveness probe."""
    return jsonify(_payload("alive")), 200
