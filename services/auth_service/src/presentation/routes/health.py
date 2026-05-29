# Health check endpoints

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify

health_bp = Blueprint("health", __name__)


def _payload(status: str, **extra):
    payload = {
        "status": status,
        "service": current_app.config.get("SERVICE_NAME", "auth_service"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    payload.update(extra)
    return payload


def _mongodb_health() -> dict:
    """Return MongoDB health status from the registered connection manager.

    Returns a minimal degraded dict when MongoDB is not wired (e.g. in-memory
    mode during development/testing).
    """
    from ...container import get_container

    try:
        container = get_container()
        if container.has_service("mongo_manager"):
            manager = container.resolve("mongo_manager")
            return manager.health_status().get("mongodb", {})
    except Exception:
        pass
    return {"status": "not_configured", "connected": False}


@health_bp.route("/health", methods=["GET"])
@health_bp.route("/api/v1/auth/health", methods=["GET"])
def health_check():
    """Basic liveness probe — always returns 200 if the process is up."""
    return jsonify(_payload("healthy")), 200


@health_bp.route("/health/ready", methods=["GET"])
@health_bp.route("/api/v1/auth/health/ready", methods=["GET"])
def readiness_check():
    """Readiness probe — returns 200 only when all dependencies are reachable.

    Checks:
      - MongoDB connectivity (via MongoConnectionManager.health_status)
      - OAuth provider registration

    Returns 503 when MongoDB is unhealthy so Kubernetes / load balancers
    can pull the pod from rotation until connectivity is restored.
    """
    from ...container import get_container

    # ── MongoDB ──────────────────────────────────────────────────────────────
    mongo_info = _mongodb_health()
    mongo_ok = mongo_info.get("status") in ("healthy", "not_configured")

    # ── OAuth providers ──────────────────────────────────────────────────────
    oauth_status = "not_configured"
    try:
        registry = get_container().resolve("oauth_provider_registry")
        names = registry.names()
        oauth_status = names if names else "not_configured"
    except Exception:
        pass

    dependencies = {
        "database": mongo_info,
        "message_queue": "not_configured",
        "oauth_providers": oauth_status,
    }

    if not mongo_ok:
        return jsonify(_payload("degraded", dependencies=dependencies)), 503

    return jsonify(_payload("ready", dependencies=dependencies)), 200


@health_bp.route("/health/live", methods=["GET"])
@health_bp.route("/api/v1/auth/health/live", methods=["GET"])
def liveness_check():
    """Liveness probe."""
    return jsonify(_payload("alive")), 200
