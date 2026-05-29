"""scripts/mongodb/ensure_indexes.py

Standalone index-provisioning script.

Run once at deployment / on every release to ensure all collection
indexes are present and up-to-date.  Safe to run multiple times
(MongoDB's createIndex is idempotent).

Usage:
    python -m scripts.mongodb.ensure_indexes --service all
    python -m scripts.mongodb.ensure_indexes --service auth_service
    python -m scripts.mongodb.ensure_indexes --service api_service
    python -m scripts.mongodb.ensure_indexes --service ai_worker

Environment variables required:
    MONGODB_URI (full connection string with credentials)

Optional per-service database name overrides:
    AUTH_SERVICE_DB      (default: auth_service)
    API_SERVICE_DB       (default: api_service)
    AI_WORKER_DB         (default: ai_worker)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# ── ensure project root on sys.path ─────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.shared_infrastructure.src.mongodb.connection import MongoConnectionManager

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("ensure_indexes")


def ensure_auth_service_indexes(manager: MongoConnectionManager) -> None:
    db_name = os.environ.get("AUTH_SERVICE_DB", "auth_service")
    db = manager.get_database(db_name)

    from services.auth_service.src.infrastructure.repositories.mongo_user_repository import (
        MongoUserRepository,
    )
    from services.auth_service.src.infrastructure.repositories.mongo_refresh_token_repository import (
        MongoRefreshTokenRepository,
    )

    MongoUserRepository(db).ensure_indexes()
    MongoRefreshTokenRepository(db).ensure_indexes()
    logger.info("auth_service indexes ✓ (db=%s)", db_name)


def ensure_api_service_indexes(manager: MongoConnectionManager) -> None:
    db_name = os.environ.get("API_SERVICE_DB", "api_service")
    db = manager.get_database(db_name)

    from services.api_service.src.infrastructure.persistence.mongodb.job_repository import (
        MongoJobRepository,
    )

    MongoJobRepository(db).ensure_indexes()
    logger.info("api_service indexes ✓ (db=%s)", db_name)


def ensure_ai_worker_indexes(manager: MongoConnectionManager) -> None:
    db_name = os.environ.get("AI_WORKER_DB", "ai_worker")
    db = manager.get_database(db_name)

    from services.ai_worker.src.infrastructure.persistence.mongodb.ai_processing_result_repository import (
        MongoAIProcessingResultRepository,
    )

    MongoAIProcessingResultRepository(db).ensure_indexes()
    logger.info("ai_worker indexes ✓ (db=%s)", db_name)


SERVICE_MAP = {
    "auth_service": ensure_auth_service_indexes,
    "api_service": ensure_api_service_indexes,
    "ai_worker": ensure_ai_worker_indexes,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision MongoDB indexes.")
    parser.add_argument(
        "--service",
        default="all",
        choices=list(SERVICE_MAP.keys()) + ["all"],
        help="Which service's indexes to provision.",
    )
    args = parser.parse_args()

    manager = MongoConnectionManager.from_env()
    manager.connect()

    try:
        targets = SERVICE_MAP.keys() if args.service == "all" else [args.service]
        for svc in targets:
            logger.info("Provisioning indexes for %s …", svc)
            SERVICE_MAP[svc](manager)
        logger.info("All indexes provisioned successfully.")
    finally:
        manager.disconnect()


if __name__ == "__main__":
    main()
