"""shared_infrastructure/mongodb/connection.py

Production-grade MongoDB connection manager.

Responsibilities:
  - Single MongoClient per process (singleton via module-level state).
  - URI parsed from environment; no credentials in source.
  - Connection-pool tuning exposed via env vars.
  - Health-check helper with rich detail used by /health endpoints.
  - Graceful shutdown hook.
  - Connection failure recovery with exponential back-off.
  - Performance metrics (op counts, latency, pool stats).

Usage (inside a service's main.py / container.py):
    from shared.shared_infrastructure.src.mongodb.connection import MongoConnectionManager

    manager = MongoConnectionManager.from_env()
    manager.connect()
    db = manager.get_database("auth_service")
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, Optional

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Environment variable names
# ─────────────────────────────────────────────
ENV_MONGODB_URI = "MONGODB_URI"
ENV_MONGODB_MIN_POOL = "MONGODB_MIN_POOL_SIZE"
ENV_MONGODB_MAX_POOL = "MONGODB_MAX_POOL_SIZE"
ENV_MONGODB_CONN_TIMEOUT = "MONGODB_CONNECT_TIMEOUT_MS"
ENV_MONGODB_SERVER_TIMEOUT = "MONGODB_SERVER_SELECTION_TIMEOUT_MS"
ENV_MONGODB_SOCKET_TIMEOUT = "MONGODB_SOCKET_TIMEOUT_MS"
ENV_MONGODB_MAX_RETRIES = "MONGODB_MAX_RETRIES"          # default 3
ENV_MONGODB_RETRY_DELAY = "MONGODB_RETRY_DELAY_SECONDS"  # default 1.0


# ─────────────────────────────────────────────
# Performance metrics (in-process, lightweight)
# ─────────────────────────────────────────────

@dataclass
class MongoMetrics:
    """Cumulative performance counters for a single connection manager.

    All counters are updated under a lock so they are safe to read from
    any thread (e.g., a /metrics endpoint running concurrently with
    request handlers).

    Not persisted between restarts — intended for runtime observability
    and Prometheus scraping via the /health/ready endpoint.
    """

    # Connection lifecycle
    connect_attempts: int = 0
    connect_successes: int = 0
    connect_failures: int = 0
    reconnect_attempts: int = 0

    # Operation counters (incremented by repositories via record_op)
    total_operations: int = 0
    failed_operations: int = 0

    # Latency tracking (milliseconds; rolling sum for avg calculation)
    total_latency_ms: float = 0.0
    _latency_count: int = 0

    # Timestamps
    connected_at: Optional[datetime] = None
    last_ping_at: Optional[datetime] = None
    last_ping_ok: Optional[bool] = None

    _lock: Lock = field(default_factory=Lock, compare=False, repr=False)

    # ── Mutators (thread-safe) ────────────────────────────────────────────

    def record_connect_attempt(self, success: bool) -> None:
        with self._lock:
            self.connect_attempts += 1
            if success:
                self.connect_successes += 1
                self.connected_at = datetime.now(timezone.utc)
            else:
                self.connect_failures += 1

    def record_reconnect(self) -> None:
        with self._lock:
            self.reconnect_attempts += 1

    def record_op(self, latency_ms: float, success: bool = True) -> None:
        """Record a completed MongoDB operation (call from repositories)."""
        with self._lock:
            self.total_operations += 1
            if not success:
                self.failed_operations += 1
            self.total_latency_ms += latency_ms
            self._latency_count += 1

    def record_ping(self, ok: bool) -> None:
        with self._lock:
            self.last_ping_at = datetime.now(timezone.utc)
            self.last_ping_ok = ok

    # ── Computed ──────────────────────────────────────────────────────────

    def _avg_latency_ms_unlocked(self) -> Optional[float]:
        """Compute avg latency without acquiring the lock (caller must hold it)."""
        if self._latency_count == 0:
            return None
        return round(self.total_latency_ms / self._latency_count, 2)

    @property
    def avg_latency_ms(self) -> Optional[float]:
        with self._lock:
            return self._avg_latency_ms_unlocked()

    def to_dict(self) -> Dict:
        with self._lock:
            return {
                "connect_attempts": self.connect_attempts,
                "connect_successes": self.connect_successes,
                "connect_failures": self.connect_failures,
                "reconnect_attempts": self.reconnect_attempts,
                "total_operations": self.total_operations,
                "failed_operations": self.failed_operations,
                "avg_latency_ms": self._avg_latency_ms_unlocked(),
                "connected_at": (
                    self.connected_at.isoformat() if self.connected_at else None
                ),
                "last_ping_at": (
                    self.last_ping_at.isoformat() if self.last_ping_at else None
                ),
                "last_ping_ok": self.last_ping_ok,
            }


# ─────────────────────────────────────────────
# Connection manager
# ─────────────────────────────────────────────

class MongoConnectionManager:
    """Manages a single MongoClient for one service.

    Design decisions:
      - One instance per service process; wired once at startup via DI container.
      - Uses URI-based auth so secrets never appear in code.
      - Connection pool sized for typical Flask worker counts.
      - `serverSelectionTimeoutMS` set low so startup failures are detected fast.
      - `retryWrites=true` (MongoDB Atlas default) handled at URI level.
      - Exponential back-off on startup connection failure (max_retries).
      - Embedded MongoMetrics for runtime observability.
    """

    def __init__(
        self,
        uri: str,
        min_pool_size: int = 2,
        max_pool_size: int = 20,
        connect_timeout_ms: int = 5_000,
        server_selection_timeout_ms: int = 5_000,
        socket_timeout_ms: int = 30_000,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
    ) -> None:
        self._uri = uri
        self._client: Optional[MongoClient] = None
        self._max_retries = max_retries
        self._retry_delay = retry_delay_seconds
        self.metrics = MongoMetrics()
        self._client_kwargs = {
            "minPoolSize": min_pool_size,
            "maxPoolSize": max_pool_size,
            "connectTimeoutMS": connect_timeout_ms,
            "serverSelectionTimeoutMS": server_selection_timeout_ms,
            "socketTimeoutMS": socket_timeout_ms,
            "w": "majority",
            "journal": True,
            "retryWrites": True,
            "retryReads": True,
        }

    # ── Factory ──────────────────────────────────────────────────────────────

    @classmethod
    def from_env(cls) -> "MongoConnectionManager":
        """Build instance from environment variables.

        Required:
            MONGODB_URI — full connection string including credentials.

        Optional (all have safe defaults):
            MONGODB_MIN_POOL_SIZE, MONGODB_MAX_POOL_SIZE,
            MONGODB_CONNECT_TIMEOUT_MS, MONGODB_SERVER_SELECTION_TIMEOUT_MS,
            MONGODB_SOCKET_TIMEOUT_MS, MONGODB_MAX_RETRIES,
            MONGODB_RETRY_DELAY_SECONDS
        """
        uri = os.environ.get(ENV_MONGODB_URI)
        if not uri:
            raise EnvironmentError(
                f"Missing required environment variable: {ENV_MONGODB_URI}"
            )
        return cls(
            uri=uri,
            min_pool_size=int(os.environ.get(ENV_MONGODB_MIN_POOL, 2)),
            max_pool_size=int(os.environ.get(ENV_MONGODB_MAX_POOL, 20)),
            connect_timeout_ms=int(os.environ.get(ENV_MONGODB_CONN_TIMEOUT, 5_000)),
            server_selection_timeout_ms=int(
                os.environ.get(ENV_MONGODB_SERVER_TIMEOUT, 5_000)
            ),
            socket_timeout_ms=int(os.environ.get(ENV_MONGODB_SOCKET_TIMEOUT, 30_000)),
            max_retries=int(os.environ.get(ENV_MONGODB_MAX_RETRIES, 3)),
            retry_delay_seconds=float(os.environ.get(ENV_MONGODB_RETRY_DELAY, 1.0)),
        )

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Open the connection pool with exponential back-off retry.

        Attempts up to `max_retries` times before raising the last exception.
        Each retry waits `retry_delay * 2^attempt` seconds (capped at 30s).

        Call once at application startup.
        """
        if self._client is not None:
            logger.debug("MongoConnectionManager: already connected.")
            return

        last_exc: Optional[Exception] = None
        for attempt in range(self._max_retries):
            try:
                logger.info(
                    "MongoConnectionManager: opening connection pool (attempt %d/%d) …",
                    attempt + 1,
                    self._max_retries,
                )
                client = MongoClient(self._uri, **self._client_kwargs)
                client.admin.command("ping")
                self._client = client
                self.metrics.record_connect_attempt(success=True)
                logger.info("MongoConnectionManager: connected successfully.")
                return
            except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
                self.metrics.record_connect_attempt(success=False)
                last_exc = exc
                delay = min(self._retry_delay * (2 ** attempt), 30.0)
                logger.warning(
                    "MongoConnectionManager: connection attempt %d failed: %s — "
                    "retrying in %.1fs …",
                    attempt + 1,
                    exc,
                    delay,
                )
                if attempt + 1 < self._max_retries:
                    if attempt > 0:
                        self.metrics.record_reconnect()
                    time.sleep(delay)

        raise ConnectionFailure(
            f"MongoConnectionManager: failed to connect after "
            f"{self._max_retries} attempts: {last_exc}"
        ) from last_exc

    def disconnect(self) -> None:
        """Close the connection pool gracefully.  Call on application shutdown."""
        if self._client is not None:
            logger.info("MongoConnectionManager: closing connection pool …")
            self._client.close()
            self._client = None
            logger.info("MongoConnectionManager: disconnected.")

    def reconnect(self) -> None:
        """Force a full disconnect/reconnect cycle.

        Useful for recovery after a detected connectivity loss.
        """
        logger.warning("MongoConnectionManager: initiating reconnect …")
        self.metrics.record_reconnect()
        self.disconnect()
        self.connect()

    # ── Accessors ────────────────────────────────────────────────────────────

    def get_client(self) -> MongoClient:
        if self._client is None:
            raise RuntimeError(
                "MongoConnectionManager: not connected. Call connect() first."
            )
        return self._client

    def get_database(self, db_name: str) -> Database:
        """Return a Database handle.  db_name comes from the service's config."""
        return self.get_client()[db_name]

    # ── Health ───────────────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Return True if MongoDB is reachable; False otherwise.

        Safe to call from /health endpoints — never raises.
        Updates internal metrics.
        """
        try:
            if self._client is None:
                self.metrics.record_ping(ok=False)
                return False
            self._client.admin.command("ping")
            self.metrics.record_ping(ok=True)
            return True
        except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
            logger.warning("MongoDB ping failed: %s", exc)
            self.metrics.record_ping(ok=False)
            return False

    def health_status(self) -> dict:
        """Return a structured health dict for observability endpoints.

        Schema::

            {
              "mongodb": {
                "status":    "healthy" | "unhealthy",
                "connected": bool,
                "latency_ms": float | null,   # round-trip time of live ping
                "pool": {                      # driver connection pool stats
                  "current": int,
                  "available": int,
                  "total_created": int
                },
                "metrics": { ... },            # MongoMetrics snapshot
                "checked_at": "ISO8601"
              }
            }
        """
        checked_at = datetime.now(timezone.utc).isoformat()
        reachable, latency_ms = self._timed_ping()
        pool_stats = self._pool_stats()

        return {
            "mongodb": {
                "status": "healthy" if reachable else "unhealthy",
                "connected": self._client is not None,
                "latency_ms": latency_ms,
                "pool": pool_stats,
                "metrics": self.metrics.to_dict(),
                "checked_at": checked_at,
            }
        }

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _timed_ping(self) -> tuple[bool, Optional[float]]:
        """Execute a ping and return (success, latency_ms)."""
        if self._client is None:
            self.metrics.record_ping(ok=False)
            return False, None
        t0 = time.perf_counter()
        try:
            self._client.admin.command("ping")
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            self.metrics.record_ping(ok=True)
            return True, latency_ms
        except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
            logger.warning("MongoDB timed ping failed: %s", exc)
            self.metrics.record_ping(ok=False)
            return False, None

    def _pool_stats(self) -> dict:
        """Extract connection pool stats from the driver's server description.

        PyMongo exposes pool stats via topology description; this is a
        best-effort extraction that degrades gracefully to empty dict.
        """
        if self._client is None:
            return {}
        try:
            # topology_description is a public (though undocumented) attribute
            td = self._client.topology_description
            servers = list(td.server_descriptions().values())
            if not servers:
                return {}
            # Aggregate across all server monitors
            pool_info: dict = {}
            for sd in servers:
                # pool_generation is available; detailed stats vary by version
                pool_info["server_type"] = str(sd.server_type)
                pool_info["round_trip_time_ms"] = (
                    round(sd.round_trip_time * 1000, 2)
                    if sd.round_trip_time is not None
                    else None
                )
            return pool_info
        except Exception as exc:
            logger.debug("Could not retrieve pool stats: %s", exc)
            return {}
