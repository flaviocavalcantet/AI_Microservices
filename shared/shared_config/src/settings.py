# Shared Configuration Base Classes

from typing import List, Optional
from pydantic import BaseSettings, Field, validator
import os


class SharedSettings(BaseSettings):
    """Base settings shared across all services
    
    Provides common configuration with validation and type safety.
    
    Environment variables have higher priority than defaults.
    Example:
        export FLASK_ENV=production
        export LOG_LEVEL=WARNING
    """
    
    # ============================================
    # ENVIRONMENT
    # ============================================
    FLASK_ENV: str = Field(
        default="development",
        description="Environment name: development, staging, production"
    )
    
    SERVICE_NAME: str = Field(
        default="api_service",
        description="Name of this service (for logging and identification)"
    )
    
    SERVICE_PORT: int = Field(
        default=5000,
        ge=1,
        le=65535,
        description="Port to run service on"
    )
    
    SERVICE_HOST: str = Field(
        default="0.0.0.0",
        description="Host address to bind to"
    )
    
    # ============================================
    # LOGGING
    # ============================================
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )
    
    LOG_FORMAT: str = Field(
        default="json",
        description="Log format: json or text"
    )
    
    # ============================================
    # DATABASE
    # ============================================
    MONGODB_URI: str = Field(
        default="mongodb://admin:admin123@localhost:27017/api_service?authSource=admin",
        description="MongoDB connection URI"
    )
    
    # ============================================
    # MESSAGE QUEUE
    # ============================================
    RABBITMQ_URL: str = Field(
        default="amqp://guest:guest@localhost:5672/",
        description="RabbitMQ connection URL"
    )
    
    # ============================================
    # CACHING
    # ============================================
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    
    # ============================================
    # SECURITY
    # ============================================
    JWT_SECRET_KEY: str = Field(
        default="dev-secret-key-only-for-testing",
        description="Secret key for JWT signing. Should be at least 32 chars in production."
    )
    
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="Algorithm for JWT signing"
    )
    
    JWT_EXPIRATION_HOURS: int = Field(
        default=24,
        ge=1,
        description="JWT token expiration time in hours"
    )
    
    # ============================================
    # CORS
    # ============================================
    CORS_ALLOWED_ORIGINS: List[str] = Field(
        default=["*"],
        description="Comma-separated list of allowed CORS origins"
    )
    
    # ============================================
    # VALIDATION
    # ============================================
    
    @validator("FLASK_ENV")
    def validate_flask_env(cls, v):
        """Validate FLASK_ENV is a known environment"""
        valid_envs = ["development", "staging", "production", "testing"]
        if v not in valid_envs:
            raise ValueError(f"FLASK_ENV must be one of: {valid_envs}")
        return v
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        """Validate LOG_LEVEL is valid"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of: {valid_levels}")
        return v.upper()
    
    @validator("LOG_FORMAT")
    def validate_log_format(cls, v):
        """Validate LOG_FORMAT"""
        valid_formats = ["json", "text"]
        if v.lower() not in valid_formats:
            raise ValueError(f"LOG_FORMAT must be one of: {valid_formats}")
        return v.lower()
    
    @validator("SERVICE_PORT", pre=True)
    def parse_service_port(cls, v):
        """Parse SERVICE_PORT from string to int"""
        if isinstance(v, str):
            return int(v)
        return v
    
    class Config:
        """Pydantic configuration"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        # Allow environment variables to override defaults
        # Example: export SERVICE_PORT=8000


class DevelopmentSettings(SharedSettings):
    """Development environment configuration
    
    DEBUG logging, permissive CORS, local services.
    """
    
    DEBUG: bool = True
    FLASK_ENV: str = "development"
    LOG_LEVEL: str = "DEBUG"
    LOG_FORMAT: str = "text"
    CORS_ALLOWED_ORIGINS: List[str] = ["*"]


class StagingSettings(SharedSettings):
    """Staging environment configuration
    
    Production-like but with permissive settings for testing.
    """
    
    DEBUG: bool = False
    FLASK_ENV: str = "staging"
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    CORS_ALLOWED_ORIGINS: List[str] = Field(
        default=[os.getenv("STAGING_FRONTEND_URL", "https://staging.company.com")],
        description="Production-like CORS for staging"
    )


class ProductionSettings(SharedSettings):
    """Production environment configuration
    
    Strict validation, required secrets, minimal logging.
    All secrets MUST come from environment variables.
    """
    
    DEBUG: bool = False
    FLASK_ENV: str = "production"
    LOG_LEVEL: str = "WARNING"
    LOG_FORMAT: str = "json"
    SWAGGER_ENABLED: bool = False
    
    # Production requires explicit CORS configuration
    CORS_ALLOWED_ORIGINS: List[str] = Field(
        default=[os.getenv("PRODUCTION_FRONTEND_URL", "https://company.com")],
        description="Strict CORS for production"
    )
    
    @validator("JWT_SECRET_KEY")
    def validate_jwt_secret_production(cls, v):
        """Production JWT secret must be strong"""
        if v == "dev-secret-key-only-for-testing":
            raise ValueError("Using development JWT secret in production!")
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters in production")
        return v
    
    @validator("MONGODB_URI")
    def validate_mongodb_uri_production(cls, v):
        """Production must have explicit MongoDB URI"""
        if not v or v.startswith("mongodb://localhost"):
            raise ValueError("Production must use explicit MongoDB URI (not localhost)")
        return v


class TestingSettings(SharedSettings):
    """Testing environment configuration
    
    In-memory/test databases, fast setup/teardown.
    """
    
    DEBUG: bool = True
    FLASK_ENV: str = "testing"
    LOG_LEVEL: str = "DEBUG"
    MONGODB_URI: str = "mongodb://admin:admin123@localhost:27017/api_service_test?authSource=admin"
    REDIS_URL: str = "redis://localhost:6379/15"  # Use separate Redis database for tests


def get_settings(env: Optional[str] = None) -> SharedSettings:
    """Get settings for environment
    
    Args:
        env: Environment name. If None, uses FLASK_ENV environment variable.
    
    Returns:
        Configuration object for the environment
    
    Raises:
        ValueError: If environment is unknown
    
    Example:
        >>> settings = get_settings()  # Uses FLASK_ENV env var
        >>> settings = get_settings("production")  # Force production
    """
    
    if env is None:
        env = os.getenv("FLASK_ENV", "development")
    
    env = env.lower().strip()
    
    settings_map = {
        "development": DevelopmentSettings,
        "dev": DevelopmentSettings,
        "staging": StagingSettings,
        "production": ProductionSettings,
        "prod": ProductionSettings,
        "testing": TestingSettings,
        "test": TestingSettings,
    }
    
    if env not in settings_map:
        valid_envs = sorted(settings_map.keys())
        raise ValueError(
            f"Unknown environment: {env}. "
            f"Valid options: {', '.join(valid_envs)}"
        )
    
    settings_class = settings_map[env]
    return settings_class()
