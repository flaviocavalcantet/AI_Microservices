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
    SERVICE_NAME: str = "auth_service"
    SERVICE_PORT: int = field(default_factory=lambda: int(os.getenv("SERVICE_PORT", 5000)))
    SERVICE_HOST: str = field(default_factory=lambda: os.getenv("SERVICE_HOST", "0.0.0.0"))

    # Logging
    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    LOG_FORMAT: str = field(default_factory=lambda: os.getenv("LOG_FORMAT", "json"))

    # Database
    MONGODB_URI: str = field(
        default_factory=lambda: os.getenv(
            "MONGODB_URI",
            "mongodb://admin:admin123@localhost:27017/auth_service?authSource=admin",
        )
    )

    # Message Queue
    RABBITMQ_URL: str = field(
        default_factory=lambda: os.getenv(
            "RABBITMQ_URL",
            "amqp://guest:guest@localhost:5672/",
        )
    )

    # Security
    JWT_SECRET_KEY: str = field(default_factory=lambda: os.getenv("JWT_SECRET_KEY", "dev-secret-key"))
    JWT_ALGORITHM: str = field(default_factory=lambda: os.getenv("JWT_ALGORITHM", "HS256"))
    JWT_ISSUER: str = field(default_factory=lambda: os.getenv("JWT_ISSUER", "auth_service"))
    JWT_AUDIENCE: str = field(default_factory=lambda: os.getenv("JWT_AUDIENCE", "ai_platform"))
    JWT_EXPIRATION_HOURS: int = field(default_factory=lambda: int(os.getenv("JWT_EXPIRATION_HOURS", 24)))
    JWT_ACCESS_TOKEN_SECONDS: int = field(
        default_factory=lambda: int(os.getenv("JWT_ACCESS_TOKEN_SECONDS", 900))
    )
    REFRESH_TOKEN_EXPIRATION_DAYS: int = field(
        default_factory=lambda: int(os.getenv("REFRESH_TOKEN_EXPIRATION_DAYS", 30))
    )

    def refresh_token_ttl_seconds(self) -> int:
        """Refresh JWT TTL in seconds — override via JWT_REFRESH_TOKEN_SECONDS env."""
        override = os.getenv("JWT_REFRESH_TOKEN_SECONDS")
        if override:
            return int(override)
        return self.REFRESH_TOKEN_EXPIRATION_DAYS * 24 * 3600
    OAUTH_STATE_TTL_MINUTES: int = field(
        default_factory=lambda: int(os.getenv("OAUTH_STATE_TTL_MINUTES", 10))
    )

    # GitHub OAuth
    GITHUB_CLIENT_ID: str = field(default_factory=lambda: os.getenv("GITHUB_CLIENT_ID", ""))
    GITHUB_CLIENT_SECRET: str = field(default_factory=lambda: os.getenv("GITHUB_CLIENT_SECRET", ""))
    GITHUB_REDIRECT_URI: str = field(
        default_factory=lambda: os.getenv(
            "GITHUB_REDIRECT_URI", "http://localhost:5000/api/v1/auth/oauth/github/callback"
        )
    )
    GITHUB_OAUTH_SCOPES: str = field(
        default_factory=lambda: os.getenv("GITHUB_OAUTH_SCOPES", "read:user user:email")
    )

    # Password hashing
    BCRYPT_LOG_ROUNDS: int = field(default_factory=lambda: int(os.getenv("BCRYPT_LOG_ROUNDS", 12)))

    # OAuth provider configuration placeholders
    OAUTH_ENABLED: bool = field(default_factory=lambda: os.getenv("OAUTH_ENABLED", "false").lower() == "true")
    OAUTH_PROVIDERS: list = field(default_factory=list)

    # Authorization placeholders
    RBAC_ENABLED: bool = field(default_factory=lambda: os.getenv("RBAC_ENABLED", "false").lower() == "true")
    DEFAULT_ROLE: str = field(default_factory=lambda: os.getenv("DEFAULT_ROLE", "user"))

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
    CORS_ALLOWED_ORIGINS: list = field(default_factory=lambda: ["*"])


@dataclass
class StagingConfig(Config):
    """Staging environment configuration"""

    FLASK_ENV: str = "staging"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
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
    MONGODB_URI: str = "mongodb://admin:admin123@localhost:27017/auth_service_test?authSource=admin"


def get_config(env: Optional[str] = None) -> Config:
    """Get configuration for environment"""

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
