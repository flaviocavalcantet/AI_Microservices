"""presentation/routes/v1/metrics.py  (auth_service)

Internal observability endpoint — exposes MongoDB performance metrics.

Intended for ops tooling, Prometheus scraping, or Grafana dashboards.
Not exposed in the public API documentation.

Routes:
    GET /api/v1/auth/metrics/mongodb
        Returns raw MongoMetrics snapshot plus connection pool info.
"""

from datetime import datetime, timezone

from flask import Blueprint, jsonify

metrics_bp = Blueprint("metrics", __name__, url_prefix="/api/v1/auth/metrics")


@metrics_bp.route("/mongodb", methods=["GET"])
def mongodb_metrics():
    """Return MongoDB performance metrics.

    Response schema::

        {
          "service": "auth_service",
          "timestamp": "ISO8601",
          "mongodb": {
            "status":          "healthy" | "unhealthy" | "not_configured",
            "connected":       bool,
            "latency_ms":      float | null,
            "pool":            { ... },
            "metrics": {
              "connect_attempts":   int,
              "connect_successes":  int,
              "connect_failures":   int,
              "reconnect_attempts": int,
              "total_operations":   int,
              "failed_operations":  int,
              "avg_latency_ms":     float | null,
              "connected_at":       "ISO8601" | null,
              "last_ping_at":       "ISO8601" | null,
              "last_ping_ok":       bool | null
            },
            "checked_at": "ISO8601"
          }
        }
    """
    from ....container import get_container

    service_name = "auth_service"
    mongo_info: dict = {"status": "not_configured", "connected": False}

    try:
        container = get_container()
        if container.has_service("mongo_manager"):
            manager = container.resolve("mongo_manager")
            mongo_info = manager.health_status().get("mongodb", mongo_info)
    except Exception as exc:
        mongo_info = {"status": "error", "error": str(exc), "connected": False}

    body = {
        "service": service_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mongodb": mongo_info,
    }

    status_code = 200 if mongo_info.get("status") in ("healthy", "not_configured") else 503
    return jsonify(body), status_code
