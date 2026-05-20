# Application entry point

import sys
import logging

from flask import Flask, jsonify
from src.infrastructure.messaging.celery_app import celery  # noqa: F401 - ensures tasks are registered

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Create minimal Flask app for health checks and status endpoints.

    The actual work is done by the Celery worker (celery-worker-ai container).
    This HTTP server exists solely for liveness/readiness probes.
    """
    app = Flask(__name__)

    @app.route("/api/v1/ai/health", methods=["GET"])
    def health():
        return jsonify({"status": "healthy", "service": "ai_worker"}), 200

    @app.route("/api/v1/ai/health/ready", methods=["GET"])
    def readiness():
        """Check broker connectivity before reporting ready."""
        try:
            conn = celery.connection(transport_options={"max_retries": 1})
            conn.ensure_connection(max_retries=1)
            conn.close()
            broker_ok = True
        except Exception:
            broker_ok = False

        status = "ready" if broker_ok else "unavailable"
        code = 200 if broker_ok else 503
        return jsonify({
            "status": status,
            "service": "ai_worker",
            "broker": "ok" if broker_ok else "unreachable",
        }), code

    return app


def main():
    try:
        app = create_app()

        logger.info("Starting ai_worker HTTP server on 0.0.0.0:5000")

        app.run(
            host="0.0.0.0",
            port=5000,
            debug=False,
            use_reloader=False,
        )

    except Exception as e:
        logger.error(f"Failed to start ai_worker: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()