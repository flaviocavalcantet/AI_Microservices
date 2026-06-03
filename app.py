"""
Flask application factory.

Usage:
    export FLASK_APP=app:create_app
    export MONGO_URI=mongodb://localhost:27017/ai_engine
    flask run
"""

from __future__ import annotations

import os

from flask import Flask
from pymongo import MongoClient

from ai_engine.infrastructure.container import create_engine
from ai_engine.interfaces.flask_routes import ai_bp


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/ai_engine")
    app.config["AI_ENGINE_MAX_WORKERS"] = int(os.getenv("AI_ENGINE_MAX_WORKERS", "4"))

    if config:
        app.config.update(config)

    # ------------------------------------------------------------------
    # MongoDB + AI engine
    # ------------------------------------------------------------------
    client = MongoClient(app.config["MONGO_URI"])
    db = client.get_default_database()

    worker = create_engine(db, max_workers=app.config["AI_ENGINE_MAX_WORKERS"])
    app.extensions["ai_engine_worker"] = worker

    # Graceful shutdown
    @app.teardown_appcontext
    def shutdown_worker(_exc):  # noqa: ANN001
        worker.shutdown(wait=False)

    # ------------------------------------------------------------------
    # Blueprints
    # ------------------------------------------------------------------
    app.register_blueprint(ai_bp)

    return app
