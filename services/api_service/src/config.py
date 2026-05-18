# Configuration management for all environments

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    """Base configuration - shared across all environments"""
    
    # Flask
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")
    DEBUG: bool = False
    TESTING: bool = False
    
    # Server
    SERVICE_NAME: str = "api_service"
    SERVICE_PORT: int = int(os.getenv("SERVICE_PORT", 5000))
    SERVICE_HOST: str = "0.0.0.0"
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "json"  # json, text
    
    # Database
    MONGODB_URI: str = os.getenv(
        "MONGODB_URI",
        "mongodb://admin:admin123@localhost:27017/api_service?authSource=admin"
    )
    
    # Message Queue
    RABBITMQ_URL: str = os.getenv(
        "RABBITMQ_URL",
        "amqp://guest:guest@localhost:5672/"
    )
    
    # Caching
    REDIS_URL: str = os.getenv(
        "REDIS_URL",
        "redis://localhost:6379/0"
    )
    
    # Security
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "dev-secret-key")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRATION_HOURS: int = 24
    
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


class DevelopmentConfig(Config):
    """Development environment configuration"""
    
    DEBUG = True
    LOG_LEVEL = "DEBUG"
    
    # Allow all origins in development
    CORS_ALLOWED_ORIGINS: list = field(default_factory=lambda: ["*"])


class StagingConfig(Config):
    """Staging environment configuration"""
    
    DEBUG = False
    LOG_LEVEL = "INFO"
    
    # Restrict CORS in staging
    CORS_ALLOWED_ORIGINS: list = field(
    default_factory=lambda: [
        os.getenv("STAGING_FRONTEND_URL", "https://staging.example.com")
    ]
)


class ProductionConfig(Config):
    """Production environment configuration"""

    DEBUG = False
    LOG_LEVEL = "WARNING"

    CORS_ALLOWED_ORIGINS: list = field(
        default_factory=lambda: [
            os.getenv("PRODUCTION_FRONTEND_URL", "https://example.com")
        ]
    )

    MONGODB_URI: str = os.getenv("MONGODB_URI", "")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")

    def __post_init__(self):
        if not self.MONGODB_URI:
            raise ValueError(
                "MONGODB_URI environment variable must be set in production"
            )

        if not self.JWT_SECRET_KEY or len(self.JWT_SECRET_KEY) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must be set and at least 32 chars in production"
            )

class TestingConfig(Config):
    """Testing environment configuration"""
    
    TESTING = True
    DEBUG = True
    LOG_LEVEL = "DEBUG"
    
    # Use in-memory database for testing
    MONGODB_URI = "mongodb://admin:admin123@localhost:27017/api_service_test?authSource=admin"


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
