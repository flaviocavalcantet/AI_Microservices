# Health check endpoints

from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__, url_prefix="/api/v1/auth")


@health_bp.route("/health", methods=["GET"])
def health_check():
    """Basic liveness probe — is the process up?"""
    return jsonify({"status": "healthy", "service": "auth_service"}), 200


@health_bp.route("/health/ready", methods=["GET"])
def readiness_check():
    """Readiness probe — is the service ready to handle traffic?

    Extend this to check MongoDB and RabbitMQ connectivity
    once those dependencies are wired up.
    """
    return jsonify({"status": "ready", "service": "auth_service"}), 200