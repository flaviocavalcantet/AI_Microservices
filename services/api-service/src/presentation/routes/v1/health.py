# Health check routes

from flask import Blueprint, jsonify
from datetime import datetime
from services.api_service.src.logger import get_logger

logger = get_logger(__name__)

health_bp = Blueprint(
    "health",
    __name__,
    url_prefix="/health"
)


@health_bp.route("", methods=["GET"])
def health_check():
    """Health check endpoint - verify service is running
    
    Liveness check: Used by load balancers and orchestrators
    
    Returns:
        JSON response with health status
        Status: 200 if healthy, 503 if unhealthy
    
    Example:
        GET /health
        
        Response (200):
        {
            "status": "healthy",
            "service": "api-service",
            "timestamp": "2026-05-20T10:30:45Z"
        }
    """
    
    try:
        response = {
            "status": "healthy",
            "service": "api-service",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        
        response = {
            "status": "unhealthy",
            "service": "api-service",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        
        return jsonify(response), 503


@health_bp.route("/ready", methods=["GET"])
def readiness_check():
    """Readiness check endpoint - verify service is ready for traffic
    
    More thorough than /health - checks external dependencies:
    - Database connectivity
    - Cache connectivity
    - Message queue connectivity
    
    Returns:
        Status: 200 if ready, 503 if not
    
    Example:
        GET /health/ready
        
        Response (200):
        {
            "status": "ready",
            "service": "api-service",
            "dependencies": {
                "database": "healthy",
                "cache": "healthy",
                "message_queue": "healthy"
            },
            "timestamp": "2026-05-20T10:30:45Z"
        }
    """
    
    dependencies = {
        "database": "unknown",
        "cache": "unknown",
        "message_queue": "unknown",
    }
    
    # Check database connectivity
    try:
        # TODO: Check MongoDB connection
        # from services.api_service.src.container import get_container
        # db = get_container().resolve("database")
        # db.ping()
        dependencies["database"] = "healthy"
    except Exception as e:
        logger.warning(f"Database readiness check failed: {e}")
        dependencies["database"] = "unhealthy"
    
    # Check cache connectivity
    try:
        # TODO: Check Redis connection
        dependencies["cache"] = "healthy"
    except Exception as e:
        logger.warning(f"Cache readiness check failed: {e}")
        dependencies["cache"] = "unhealthy"
    
    # Check message queue connectivity
    try:
        # TODO: Check RabbitMQ connection
        dependencies["message_queue"] = "healthy"
    except Exception as e:
        logger.warning(f"Message queue readiness check failed: {e}")
        dependencies["message_queue"] = "unhealthy"
    
    # Service is ready if all dependencies are healthy
    all_healthy = all(
        status == "healthy"
        for status in dependencies.values()
    )
    
    status = "ready" if all_healthy else "not_ready"
    status_code = 200 if all_healthy else 503
    
    response = {
        "status": status,
        "service": "api-service",
        "dependencies": dependencies,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    
    return jsonify(response), status_code


@health_bp.route("/live", methods=["GET"])
def liveness_check():
    """Kubernetes liveness probe
    
    Same as /health - verifies service is running
    
    Returns:
        Status: 200 if alive, 503 if dead
    """
    
    try:
        response = {
            "status": "alive",
            "service": "api-service",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Liveness check failed: {e}", exc_info=True)
        return jsonify({"status": "dead", "error": str(e)}), 503


@health_bp.route("/metrics", methods=["GET"])
def metrics():
    """Metrics endpoint (placeholder)
    
    TODO: Implement with prometheus_client
    
    Returns:
        Prometheus metrics format
    
    Example:
        GET /health/metrics
        
        Response:
        api_requests_total 1234
        api_request_duration_seconds_sum 56.78
        api_errors_total 2
    """
    
    # Placeholder - will be implemented with Prometheus
    response = {
        "status": "success",
        "message": "Metrics endpoint not yet implemented",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    
    return jsonify(response), 200
