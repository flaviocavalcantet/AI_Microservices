# Health check blueprint

from flask import Blueprint, jsonify, current_app, g
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

health_bp = Blueprint(
    "health",
    __name__,
    url_prefix="/health"
)


@health_bp.route("", methods=["GET"])
def health_check():
    """Health check endpoint - verify service is running
    
    Returns basic service health information.
    Used by load balancers and orchestrators for liveliness checks.
    
    Returns:
        JSON with service health status
        Status: 200 if healthy, 503 if unhealthy
    """
    
    try:
        response = {
            "status": "healthy",
            "service": current_app.config.get("SERVICE_NAME", "api_service"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        
        response = {
            "status": "unhealthy",
            "service": current_app.config.get("SERVICE_NAME", "api_service"),
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        
        return jsonify(response), 503


@health_bp.route("/ready", methods=["GET"])
def readiness_check():
    """Readiness check endpoint - verify service is ready to handle requests
    
    More thorough check than /health - verifies external dependencies
    (database, cache, message queue) are available.
    
    Used by orchestrators to determine if service should receive traffic.
    
    Returns:
        JSON with readiness status and dependency health
        Status: 200 if ready, 503 if not ready
    """
    
    dependencies = {
        "database": "unknown",
        "cache": "unknown",
        "message_queue": "unknown",
    }
    
    # Check database connectivity (placeholder)
    try:
        # TODO: Check MongoDB connection
        dependencies["database"] = "healthy"
    except Exception as e:
        logger.warning(f"Database readiness check failed: {e}")
        dependencies["database"] = "unhealthy"
    
    # Check cache connectivity (placeholder)
    try:
        # TODO: Check Redis connection
        dependencies["cache"] = "healthy"
    except Exception as e:
        logger.warning(f"Cache readiness check failed: {e}")
        dependencies["cache"] = "unhealthy"
    
    # Check message queue connectivity (placeholder)
    try:
        # TODO: Check RabbitMQ connection
        dependencies["message_queue"] = "healthy"
    except Exception as e:
        logger.warning(f"Message queue readiness check failed: {e}")
        dependencies["message_queue"] = "unhealthy"
    
    # Service is ready if all critical dependencies are healthy
    all_healthy = all(
        status == "healthy"
        for status in dependencies.values()
    )
    
    response = {
        "status": "ready" if all_healthy else "not_ready",
        "service": current_app.config.get("SERVICE_NAME", "api_service"),
        "dependencies": dependencies,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    
    status_code = 200 if all_healthy else 503
    return jsonify(response), status_code


@health_bp.route("/live", methods=["GET"])
def liveness_check():
    """Liveness check endpoint - Kubernetes liveness probe
    
    Lightweight check to verify service process is alive.
    Kubernetes will restart the pod if this fails.
    
    Returns:
        JSON with liveness status
        Status: 200 if alive, 500 if dead
    """
    
    try:
        response = {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Liveness check failed: {e}", exc_info=True)
        return jsonify({"status": "dead", "error": str(e)}), 500


@health_bp.route("/metrics", methods=["GET"])
def metrics_summary():
    """Metrics summary endpoint - basic health metrics
    
    Returns:
        JSON with basic service metrics
    """
    
    response = {
        "service": current_app.config.get("SERVICE_NAME", "api_service"),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "metrics": {
            # Placeholder for actual metrics
            "requests_total": 0,
            "requests_in_progress": 0,
            "errors_total": 0,
            "uptime_seconds": 0,
        }
    }
    
    return jsonify(response), 200
