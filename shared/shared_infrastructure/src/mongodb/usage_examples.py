"""shared_infrastructure/mongodb/usage_examples.py

Examples of using the MongoDB infrastructure with the new components.

This module demonstrates:
1. Using MongoDBConfig for validated configuration
2. Creating MongoConnectionManager from config
3. Using ObjectIdWrapper for ID handling
4. Implementing repositories with DI
"""

from __future__ import annotations

import os

from pymongo.database import Database

from .config import MongoDBConfig
from .connection import MongoConnectionManager
from .object_id_wrapper import ObjectIdWrapper, wrap_id

# ───────────────────────────────────────────────────────────────────────────────
# Example 1: Service Startup with MongoDBConfig
# ───────────────────────────────────────────────────────────────────────────────

def example_service_startup() -> None:
    """Typical service startup pattern using MongoDBConfig."""

    # Load and validate configuration from environment
    config = MongoDBConfig.from_env()
    print(f"Configuration: {config}")

    # Create connection manager from validated config
    manager = config.create_connection_manager()

    # Establish connection at startup
    manager.connect()

    # Get database handle (each service has its own DB)
    db = manager.get_database("auth_service")

    # Register repositories with DI container
    from shared.shared_infrastructure.src.mongodb import MongoBaseRepository

    print(f"✓ Connected to {db.name}")

    # Cleanup on shutdown
    manager.disconnect()


# ───────────────────────────────────────────────────────────────────────────────
# Example 2: Environment-Specific Configuration
# ───────────────────────────────────────────────────────────────────────────────

def example_environment_configs() -> None:
    """Create configurations for different environments."""

    # Development (small pool, fast timeouts for feedback)
    dev_config = MongoDBConfig.for_development(
        mongodb_uri="mongodb://admin:admin123@localhost:27017/auth_service?authSource=admin"
    )
    print(f"Dev pool: {dev_config.resolve_pool_sizes()}")
    # Output: (1, 10) — min=1, max=10

    # Staging (medium pool, standard timeouts)
    staging_config = MongoDBConfig.for_staging(
        mongodb_uri="mongodb://admin:password@staging-mongo.internal:27017/auth_service?authSource=admin"
    )
    print(f"Staging pool: {staging_config.resolve_pool_sizes()}")
    # Output: (2, 20) — min=2, max=20

    # Production (large pool, long timeouts for reliability)
    prod_config = MongoDBConfig.for_production(
        mongodb_uri="mongodb://admin:password@prod-mongo.internal:27017/auth_service?authSource=admin"
    )
    print(f"Production pool: {prod_config.resolve_pool_sizes()}")
    # Output: (5, 50) — min=5, max=50


# ───────────────────────────────────────────────────────────────────────────────
# Example 3: Custom Configuration Override
# ───────────────────────────────────────────────────────────────────────────────

def example_custom_config() -> None:
    """Override specific configuration values."""

    # Start with development defaults, but customize pool size
    config = MongoDBConfig.for_development(
        mongodb_uri="mongodb://admin:admin123@localhost:27017/api_service?authSource=admin",
        min_pool_size=5,  # Override: increase min pool
        max_pool_size=30,  # Override: increase max pool
    )

    print(f"Custom pool: {config.resolve_pool_sizes()}")
    # Output: (5, 30) — custom values, not dev defaults


# ───────────────────────────────────────────────────────────────────────────────
# Example 4: ObjectIdWrapper Usage
# ───────────────────────────────────────────────────────────────────────────────

def example_object_id_wrapper() -> None:
    """Demonstrate ObjectIdWrapper for ID handling."""

    # Create wrapper from string UUID (current approach)
    string_id = "550e8400-e29b-41d4-a716-446655440000"
    wrapped = ObjectIdWrapper.from_string(string_id)

    # Get as string (default for domain layer)
    print(f"As string: {wrapped.as_string()}")
    # Output: 550e8400-e29b-41d4-a716-446655440000

    # Convert to ObjectId for raw MongoDB queries (if needed)
    # obj_id = wrapped.as_object_id()  # May fail if not valid hex

    # Check if convertible to ObjectId
    is_valid = wrapped.is_valid_object_id()
    print(f"Valid ObjectId? {is_valid}")

    # Convenience wrapper function
    wrapped2 = wrap_id(string_id)
    print(f"Created with wrap_id: {wrapped2}")

    # ObjectIds can be wrapped directly
    from bson import ObjectId

    oid = ObjectId()
    wrapped3 = ObjectIdWrapper.from_object_id(oid)
    print(f"From ObjectId: {wrapped3.as_string()}")


# ───────────────────────────────────────────────────────────────────────────────
# Example 5: Repository Pattern with Config
# ───────────────────────────────────────────────────────────────────────────────

def example_repository_with_config() -> None:
    """Show how repositories integrate with MongoDBConfig."""

    from shared.shared_infrastructure.src.mongodb import MongoBaseRepository

    # Load config and create manager
    config = MongoDBConfig.from_env()
    manager = config.create_connection_manager()
    manager.connect()

    # Get database
    db = manager.get_database("auth_service")

    # Repositories receive injected Database handle
    # (they don't know about MongoDBConfig or MongoConnectionManager)
    # from services.auth_service.src.infrastructure.repositories import MongoUserRepository
    # user_repo = MongoUserRepository(db)

    manager.disconnect()


# ───────────────────────────────────────────────────────────────────────────────
# Example 6: Configuration Validation
# ───────────────────────────────────────────────────────────────────────────────

def example_configuration_validation() -> None:
    """Demonstrate configuration validation."""

    from pydantic import ValidationError

    # Valid configuration
    try:
        config = MongoDBConfig(
            mongodb_uri="mongodb://admin:pass@localhost:27017/mydb?authSource=admin",
            environment="production",
        )
        print(f"✓ Valid config: {config}")
    except ValidationError as e:
        print(f"✗ Invalid config: {e}")

    # Invalid: bad environment
    try:
        config = MongoDBConfig(
            mongodb_uri="mongodb://admin:pass@localhost:27017/mydb?authSource=admin",
            environment="invalid_env",  # ✗ Must be: development, staging, production
        )
    except ValidationError as e:
        print(f"✗ Invalid environment: caught by Pydantic")

    # Invalid: missing URI
    try:
        config = MongoDBConfig(
            mongodb_uri="",  # ✗ Cannot be empty
            environment="development",
        )
    except ValidationError as e:
        print(f"✗ Missing URI: caught by Pydantic")


# ───────────────────────────────────────────────────────────────────────────────
# Example 7: Integration with Application Factory (Flask)
# ───────────────────────────────────────────────────────────────────────────────

def example_flask_factory_pattern() -> None:
    """Show how to use in Flask application factory."""

    # In a service's main application factory (e.g., presentation/app.py or container.py)

    from flask import Flask

    def create_app(env: str = "development") -> Flask:
        """Flask application factory."""
        app = Flask(__name__)

        # Load and validate MongoDB configuration
        config = MongoDBConfig.from_env()

        # Create connection manager
        manager = config.create_connection_manager()
        manager.connect()

        # Store manager in app context
        app.mongo_manager = manager

        # Get database handles
        auth_db = manager.get_database("auth_service")
        api_db = manager.get_database("api_service")

        # Register repositories with DI container
        # container = ServiceContainer()
        # register_mongo_repositories(container, auth_db)
        # app.container = container

        @app.teardown_appcontext
        def teardown_mongodb(exc=None):
            """Close MongoDB on app shutdown."""
            if hasattr(app, "mongo_manager"):
                app.mongo_manager.disconnect()

        @app.route("/health")
        def health_check():
            """Health check endpoint."""
            health = app.mongo_manager.health_status()
            return health

        return app

    # app = create_app()
    # app.run()


# ───────────────────────────────────────────────────────────────────────────────
# Example 8: Configuration in docker-compose.yml
# ───────────────────────────────────────────────────────────────────────────────

"""
In docker-compose.yml, set environment variables:

services:
  auth_service:
    environment:
      MONGODB_URI: mongodb://admin:admin123@mongodb:27017/auth_service?authSource=admin
      MONGODB_ENVIRONMENT: development
      MONGODB_MIN_POOL_SIZE: 2
      MONGODB_MAX_POOL_SIZE: 20

Then in your service:
  config = MongoDBConfig.from_env()  # Loads from environment
  manager = config.create_connection_manager()
  manager.connect()
"""


# ───────────────────────────────────────────────────────────────────────────────
# Example 9: Safe Configuration Display (for logging)
# ───────────────────────────────────────────────────────────────────────────────

def example_safe_config_logging() -> None:
    """Log configuration without exposing credentials."""

    config = MongoDBConfig.for_development(
        mongodb_uri="mongodb://admin:secret_password@localhost:27017/mydb?authSource=admin"
    )

    # Never log the raw config (contains credentials)
    # print(config.mongodb_uri)  # ✗ Bad: exposes password

    # Use safe representation instead
    safe_dict = config.to_dict_safe()
    print(f"Configuration: {safe_dict}")
    # Output: {'mongodb_uri': '***@***', 'environment': 'development', ...}

    # Or use string representation
    print(f"Config: {config}")
    # Output: MongoDBConfig(env=development, uri=***@***, pool=(1, 10))


if __name__ == "__main__":
    print("MongoDB Infrastructure Usage Examples\n")
    print("=" * 60)

    print("\n1. Example: Service Startup")
    print("-" * 60)
    # example_service_startup()  # Requires MONGODB_URI env var

    print("\n2. Example: Environment Configs")
    print("-" * 60)
    example_environment_configs()

    print("\n3. Example: Custom Config Override")
    print("-" * 60)
    example_custom_config()

    print("\n4. Example: ObjectIdWrapper")
    print("-" * 60)
    example_object_id_wrapper()

    print("\n5. Example: Configuration Validation")
    print("-" * 60)
    example_configuration_validation()

    print("\n6. Example: Safe Config Logging")
    print("-" * 60)
    example_safe_config_logging()

    print("\n" + "=" * 60)
    print("See function docstrings for more details")
