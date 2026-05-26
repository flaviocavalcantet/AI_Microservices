# Configuration management for all environments

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    """Base configuration - shared across all environments"""
    
    # Flask
    FLASK_ENV: str = field(default_factory=lambda: os.getenv("FLASK_ENV", "development"))
    DEBUG: bool = False
    TESTING: bool = False
    
    # Server
    SERVICE_NAME: str = "api_service"
    SERVICE_PORT: int = field(default_factory=lambda: int(os.getenv("SERVICE_PORT", 5000)))
    SERVICE_HOST: str = field(default_factory=lambda: os.getenv("SERVICE_HOST", "0.0.0.0"))
    
    # Logging
    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    LOG_FORMAT: str = field(default_factory=lambda: os.getenv("LOG_FORMAT", "json"))  # json, text
    
    # Database
    MONGODB_URI: str = field(
        default_factory=lambda: os.getenv(
            "MONGODB_URI",
            "mongodb://admin:admin123@localhost:27017/api_service?authSource=admin",
        )
    )
    
    # Message Queue
    RABBITMQ_URL: str = field(
        default_factory=lambda: os.getenv(
            "RABBITMQ_URL",
            "amqp://guest:guest@localhost:5672/",
        )
    )
    
    # Caching
    REDIS_URL: str = field(
        default_factory=lambda: os.getenv(
            "REDIS_URL",
            "redis://localhost:6379/0",
        )
    )
    
    # Security / JWT (must match auth-service issuance settings)
    JWT_SECRET_KEY: str = field(default_factory=lambda: os.getenv("JWT_SECRET_KEY", "dev-secret-key"))
    JWT_ALGORITHM: str = field(default_factory=lambda: os.getenv("JWT_ALGORITHM", "HS256"))
    JWT_ISSUER: str = field(default_factory=lambda: os.getenv("JWT_ISSUER", "auth_service"))
    JWT_AUDIENCE: str = field(default_factory=lambda: os.getenv("JWT_AUDIENCE", "ai_platform"))
    JWT_EXPIRATION_HOURS: int = field(default_factory=lambda: int(os.getenv("JWT_EXPIRATION_HOURS", 24)))
    JWT_AUTH_ENABLED: bool = field(
        default_factory=lambda: os.getenv("JWT_AUTH_ENABLED", "true").lower() == "true"
    )
    JWT_AUTH_REQUIRED: bool = field(
        default_factory=lambda: os.getenv("JWT_AUTH_REQUIRED", "false").lower() == "true"
    )

    # SPIFFE / SPIRE (Docker workload identity)
    SPIRE_ENABLED: bool = field(
        default_factory=lambda: os.getenv("SPIRE_ENABLED", "false").lower() == "true"
    )
    SPIRE_TRUST_DOMAIN: str = field(
        default_factory=lambda: os.getenv("SPIRE_TRUST_DOMAIN", "ai-platform.local")
    )
    SPIRE_AGENT_SOCKET: str = field(
        default_factory=lambda: os.getenv(
            "SPIRE_AGENT_SOCKET", "unix:///tmp/spire-agent/public/api.sock"
        )
    )
    SPIRE_WORKLOAD_ID: str = field(
        default_factory=lambda: os.getenv(
            "SPIRE_WORKLOAD_ID", "spiffe://ai-platform.local/workload/api-service"
        )
    )
    
    # CORS
    CORS_ALLOWED_ORIGINS: list = field(default_factory=list)
    
    # API Documentation
    SWAGGER_ENABLED: bool = True
    OPENAPI_VERSION: str = "3.0.3"
    
    # Health Check
    HEALTH_CHECK_ENABLED: bool = True
    
    # Error Handling
    PROPAGATE_EXCEPTIONS: bool = True
    JSON_SORT_KEYS: bool = False


@dataclass
class DevelopmentConfig(Config):
    """Development environment configuration"""
    
    FLASK_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    
    # Allow all origins in development
    CORS_ALLOWED_ORIGINS: list = field(default_factory=lambda: ["*"])


@dataclass
class StagingConfig(Config):
    """Staging environment configuration"""
    
    FLASK_ENV: str = "staging"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # Restrict CORS in staging
    CORS_ALLOWED_ORIGINS: list = field(
    default_factory=lambda: [
        os.getenv("STAGING_FRONTEND_URL", "https://staging.example.com")
    ]
)


@dataclass
class ProductionConfig(Config):
    """Production environment configuration"""

    FLASK_ENV: str = "production"
    DEBUG: bool = False
    LOG_LEVEL: str = "WARNING"

    CORS_ALLOWED_ORIGINS: list = field(
        default_factory=lambda: [
            os.getenv("PRODUCTION_FRONTEND_URL", "https://example.com")
        ]
    )

    MONGODB_URI: str = field(default_factory=lambda: os.getenv("MONGODB_URI", ""))
    JWT_SECRET_KEY: str = field(default_factory=lambda: os.getenv("JWT_SECRET_KEY", ""))

    def __post_init__(self):
        if not self.MONGODB_URI:
            raise ValueError(
                "MONGODB_URI environment variable must be set in production"
            )

        if not self.JWT_SECRET_KEY or len(self.JWT_SECRET_KEY) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must be set and at least 32 chars in production"
            )

@dataclass
class TestingConfig(Config):
    """Testing environment configuration"""
    
    FLASK_ENV: str = "testing"
    TESTING: bool = True
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    
    # Use in-memory database for testing
    MONGODB_URI: str = "mongodb://admin:admin123@localhost:27017/api_service_test?authSource=admin"


def get_config(env: Optional[str] = None) -> Config:
    """Get configuration for environment
    
    Args:
        env: Environment name (development, staging, production, testing)
             If None, uses FLASK_ENV environment variable
    
    Returns:
        Configuration object for the environment
    
    Raises:
        ValueError: If environment is unknown
    """
    if env is None:
        env = os.getenv("FLASK_ENV", "development")
    
    env = env.lower().strip()
    
    config_map = {
        "development": DevelopmentConfig,
        "dev": DevelopmentConfig,
        "staging": StagingConfig,
        "production": ProductionConfig,
        "prod": ProductionConfig,
        "testing": TestingConfig,
        "test": TestingConfig,
    }
    
    if env not in config_map:
        raise ValueError(
            f"Unknown environment: {env}. "
            f"Valid options: {', '.join(config_map.keys())}"
        )
    
    return config_map[env]()
