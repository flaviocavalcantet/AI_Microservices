"""shared_infrastructure/mongodb/config.py

Pydantic-based MongoDB configuration with environment-aware validation.

Replaces ad-hoc environment variable parsing with structured, validated config.
Supports development, staging, and production environments with different pool
sizing and timeout strategies.

Usage:
    # Load from environment
    config = MongoDBConfig.from_env()

    # Or explicitly
    config = MongoDBConfig(
        mongodb_uri="mongodb://admin:pass@localhost:27017/my_db?authSource=admin",
        min_pool_size=2,
        max_pool_size=20,
        environment="production"
    )

    # Create connection manager
    manager = config.create_connection_manager()
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from pydantic import BaseModel, Field, validator

from .connection import MongoConnectionManager

logger = logging.getLogger(__name__)


class MongoDBConfig(BaseModel):
    """Validated MongoDB configuration.

    Attributes:
        mongodb_uri: Full connection string (required).
            Must contain credentials and database name.
            Example: mongodb://user:pass@host:27017/dbname?authSource=admin

        environment: Deployment environment (dev, staging, production).
            Controls pool sizing and timeout defaults.
            Default: development

        min_pool_size: Minimum connection pool size.
            Dev: 1, Staging: 2, Production: 5

        max_pool_size: Maximum connection pool size.
            Dev: 10, Staging: 20, Production: 50

        connect_timeout_ms: Time to establish initial connection.
            Dev: 5000ms, Staging: 5000ms, Production: 10000ms

        server_selection_timeout_ms: Time to find a suitable server.
            Dev: 5000ms, Staging: 5000ms, Production: 10000ms

        socket_timeout_ms: Time for operations on a socket.
            Dev: 30000ms, Staging: 30000ms, Production: 60000ms
    """

    mongodb_uri: str = Field(
        ...,
        description="MongoDB connection URI with credentials",
        example="mongodb://admin:password@localhost:27017/mydb?authSource=admin",
    )

    environment: str = Field(
        default="development",
        description="Deployment environment: development, staging, production",
        regex="^(development|staging|production)$",
    )

    min_pool_size: Optional[int] = Field(
        default=None,
        ge=1,
        le=100,
        description="Minimum connection pool size (auto-set by environment if None)",
    )

    max_pool_size: Optional[int] = Field(
        default=None,
        ge=1,
        le=500,
        description="Maximum connection pool size (auto-set by environment if None)",
    )

    connect_timeout_ms: Optional[int] = Field(
        default=None,
        ge=1000,
        le=60000,
        description="Connection timeout in milliseconds",
    )

    server_selection_timeout_ms: Optional[int] = Field(
        default=None,
        ge=1000,
        le=60000,
        description="Server selection timeout in milliseconds",
    )

    socket_timeout_ms: Optional[int] = Field(
        default=None,
        ge=1000,
        le=300000,
        description="Socket timeout in milliseconds",
    )

    class Config:
        """Pydantic configuration."""

        env_prefix = "MONGODB_"
        case_sensitive = False
        extra = "forbid"  # Reject unknown fields
        schema_extra = {
            "example": {
                "mongodb_uri": "mongodb://admin:pass@localhost:27017/auth_service?authSource=admin",
                "environment": "development",
                "min_pool_size": 2,
                "max_pool_size": 20,
            }
        }

    @validator("mongodb_uri")
    def validate_uri(cls, value: str) -> str:
        """Validate MongoDB URI format."""
        if not value or not value.startswith("mongodb"):
            raise ValueError(
                "mongodb_uri must be a valid MongoDB connection string "
                "(starting with 'mongodb://' or 'mongodb+srv://')"
            )
        if "://" not in value:
            raise ValueError("mongodb_uri must contain '://' (malformed)")
        return value

    @validator("environment")
    def validate_environment(cls, value: str) -> str:
        """Normalize environment name."""
        return value.lower()

    # ── Factory methods ──────────────────────────────────────────────────────

    @classmethod
    def from_env(cls) -> MongoDBConfig:
        """Load configuration from environment variables.

        Expected variables:
            MONGODB_URI (required)
            MONGODB_ENVIRONMENT (optional, default: development)
            MONGODB_MIN_POOL_SIZE (optional, auto-set if not provided)
            MONGODB_MAX_POOL_SIZE (optional, auto-set if not provided)
            MONGODB_CONNECT_TIMEOUT_MS (optional, auto-set if not provided)
            MONGODB_SERVER_SELECTION_TIMEOUT_MS (optional, auto-set if not provided)
            MONGODB_SOCKET_TIMEOUT_MS (optional, auto-set if not provided)

        Raises:
            ValueError: If MONGODB_URI is not set or validation fails.

        Returns:
            MongoDBConfig instance with values from environment.
        """
        uri = os.environ.get("MONGODB_URI")
        if not uri:
            raise ValueError(
                "Required environment variable MONGODB_URI not set. "
                "Example: mongodb://admin:pass@localhost:27017/dbname?authSource=admin"
            )

        environment = os.environ.get("MONGODB_ENVIRONMENT", "development").lower()

        # Parse optional values, with environment-based defaults
        min_pool_size = os.environ.get("MONGODB_MIN_POOL_SIZE")
        max_pool_size = os.environ.get("MONGODB_MAX_POOL_SIZE")
        connect_timeout = os.environ.get("MONGODB_CONNECT_TIMEOUT_MS")
        server_selection_timeout = os.environ.get("MONGODB_SERVER_SELECTION_TIMEOUT_MS")
        socket_timeout = os.environ.get("MONGODB_SOCKET_TIMEOUT_MS")

        config = cls(
            mongodb_uri=uri,
            environment=environment,
            min_pool_size=int(min_pool_size) if min_pool_size else None,
            max_pool_size=int(max_pool_size) if max_pool_size else None,
            connect_timeout_ms=int(connect_timeout) if connect_timeout else None,
            server_selection_timeout_ms=(
                int(server_selection_timeout) if server_selection_timeout else None
            ),
            socket_timeout_ms=int(socket_timeout) if socket_timeout else None,
        )
        logger.info(
            "MongoDBConfig loaded from environment (env=%s, uri_host=***)",
            environment,
        )
        return config

    @classmethod
    def for_development(
        cls, mongodb_uri: str, **kwargs
    ) -> MongoDBConfig:
        """Create a development configuration."""
        return cls(
            mongodb_uri=mongodb_uri,
            environment="development",
            **kwargs,
        )

    @classmethod
    def for_staging(
        cls, mongodb_uri: str, **kwargs
    ) -> MongoDBConfig:
        """Create a staging configuration."""
        return cls(
            mongodb_uri=mongodb_uri,
            environment="staging",
            **kwargs,
        )

    @classmethod
    def for_production(
        cls, mongodb_uri: str, **kwargs
    ) -> MongoDBConfig:
        """Create a production configuration."""
        return cls(
            mongodb_uri=mongodb_uri,
            environment="production",
            **kwargs,
        )

    # ── Configuration resolution ─────────────────────────────────────────────

    def resolve_pool_sizes(self) -> tuple[int, int]:
        """Get (min_pool_size, max_pool_size) with environment defaults.

        Development:
            min=1, max=10

        Staging:
            min=2, max=20

        Production:
            min=5, max=50
        """
        env_defaults = {
            "development": (1, 10),
            "staging": (2, 20),
            "production": (5, 50),
        }

        default_min, default_max = env_defaults.get(
            self.environment, env_defaults["development"]
        )

        return (
            self.min_pool_size or default_min,
            self.max_pool_size or default_max,
        )

    def resolve_timeouts(self) -> tuple[int, int, int]:
        """Get (connect, server_selection, socket) timeouts with environment defaults.

        Development:
            connect=5000ms, server_selection=5000ms, socket=30000ms

        Staging:
            connect=5000ms, server_selection=5000ms, socket=30000ms

        Production:
            connect=10000ms, server_selection=10000ms, socket=60000ms
        """
        env_defaults = {
            "development": (5000, 5000, 30000),
            "staging": (5000, 5000, 30000),
            "production": (10000, 10000, 60000),
        }

        defaults = env_defaults.get(
            self.environment, env_defaults["development"]
        )

        return (
            self.connect_timeout_ms or defaults[0],
            self.server_selection_timeout_ms or defaults[1],
            self.socket_timeout_ms or defaults[2],
        )

    # ── Connection manager creation ──────────────────────────────────────────

    def create_connection_manager(self) -> MongoConnectionManager:
        """Create a MongoConnectionManager from this configuration.

        Returns:
            Configured MongoConnectionManager instance.
        """
        min_pool, max_pool = self.resolve_pool_sizes()
        connect_timeout, server_timeout, socket_timeout = self.resolve_timeouts()

        manager = MongoConnectionManager(
            uri=self.mongodb_uri,
            min_pool_size=min_pool,
            max_pool_size=max_pool,
            connect_timeout_ms=connect_timeout,
            server_selection_timeout_ms=server_timeout,
            socket_timeout_ms=socket_timeout,
        )

        logger.info(
            "MongoConnectionManager created (env=%s, pool=%d-%d, "
            "timeouts=%dms/%dms/%dms)",
            self.environment,
            min_pool,
            max_pool,
            connect_timeout,
            server_timeout,
            socket_timeout,
        )
        return manager

    def __str__(self) -> str:
        """String representation (hides credentials)."""
        return (
            f"MongoDBConfig(env={self.environment}, uri=***@***, "
            f"pool={self.resolve_pool_sizes()})"
        )

    def to_dict_safe(self) -> dict:
        """Return config as dict with credentials masked."""
        return {
            "mongodb_uri": "***@***",
            "environment": self.environment,
            "min_pool_size": self.resolve_pool_sizes()[0],
            "max_pool_size": self.resolve_pool_sizes()[1],
            "connect_timeout_ms": self.resolve_timeouts()[0],
            "server_selection_timeout_ms": self.resolve_timeouts()[1],
            "socket_timeout_ms": self.resolve_timeouts()[2],
        }
