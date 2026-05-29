"""infrastructure/persistence/mongodb/mongo_wiring.py  (auth_service)

Registers MongoDB-backed repository implementations into the service's
DI container, replacing the in-memory stubs used in development.

Responsibilities:
  - Build concrete MongoDB repositories with the shared Database handle.
  - Call ``repository.initialize()`` on each repo so that collection indexes
    are created **before** the first request arrives (eager startup, not lazy).
  - Pass the MongoConnectionManager to repositories so per-operation metrics
    are recorded automatically.
  - Expose a ``teardown_mongo`` helper for graceful shutdown.

Call ``wire_mongo(container, db, connection_manager)`` from the application
factory (presentation/app.py) when MONGODB_URI is configured.

This file is the ONLY place in auth_service that knows both about the
DI container *and* the concrete MongoDB repository classes.
"""

from __future__ import annotations

import logging

from pymongo.database import Database

from ...container import ServiceContainer

logger = logging.getLogger(__name__)


def wire_mongo(
    container: ServiceContainer,
    db: Database,
    connection_manager=None,
) -> None:
    """Wire MongoDB repositories into the service container and initialise indexes.

    Args:
        container: The service DI container.
        db: Pymongo Database handle for the auth service database.
        connection_manager: Optional MongoConnectionManager.  When supplied,
            per-operation latency metrics are forwarded to its MongoMetrics
            instance and the manager itself is registered as ``mongo_manager``
            so the health endpoint can call ``health_status()`` on it.

    After this call:
      - ``container.resolve("user_repository")``         → MongoUserRepository
      - ``container.resolve("refresh_token_repository")`` → MongoRefreshTokenRepository
      - ``container.resolve("mongo_manager")``           → MongoConnectionManager (if given)
    """
    from .mongo_user_repository import MongoUserRepository
    from .mongo_refresh_token_repository import MongoRefreshTokenRepository

    # Build repositories, injecting the connection manager for metrics
    user_repo = MongoUserRepository(db, connection_manager=connection_manager)
    refresh_token_repo = MongoRefreshTokenRepository(db, connection_manager=connection_manager)

    # ── Eager index creation ─────────────────────────────────────────────────
    # initialize() calls ensure_indexes() and marks the repo as ready.
    # Errors are logged but do not abort startup (indexes are still best-effort).
    logger.info("wire_mongo: initialising collection indexes …")
    user_repo.initialize()
    refresh_token_repo.initialize()
    logger.info("wire_mongo: index initialisation complete.")

    # ── Register in DI container ─────────────────────────────────────────────
    container.register_instance("user_repository", user_repo)
    container.register_instance("refresh_token_repository", refresh_token_repo)

    if connection_manager is not None:
        container.register_instance("mongo_manager", connection_manager)

    logger.info(
        "wire_mongo: repositories registered (db=%s, collections=%s)",
        db.name,
        [MongoUserRepository.COLLECTION_NAME, MongoRefreshTokenRepository.COLLECTION_NAME],
    )


def teardown_mongo(container: ServiceContainer) -> None:
    """Gracefully disconnect MongoDB on application shutdown.

    Call from the Flask ``teardown_appcontext`` or ``atexit`` hook.
    """
    if not container.has_service("mongo_manager"):
        return
    try:
        manager = container.resolve("mongo_manager")
        manager.disconnect()
        logger.info("teardown_mongo: MongoDB connection closed.")
    except Exception as exc:
        logger.warning("teardown_mongo: error during disconnect: %s", exc)


# ---------------------------------------------------------------------------
# Backwards-compatibility alias
# ---------------------------------------------------------------------------
# The old name ``register_mongo_repositories`` is preserved so that any
# existing call sites continue to work.  New code should use ``wire_mongo``.

def register_mongo_repositories(container: ServiceContainer, db: Database) -> None:  # noqa: E501
    """Deprecated: use wire_mongo() instead."""
    logger.warning(
        "register_mongo_repositories() is deprecated; use wire_mongo() instead."
    )
    wire_mongo(container, db, connection_manager=None)
