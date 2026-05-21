"""Configuration for notification-service."""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    """Base configuration shared by HTTP probes and event consumers."""

    FLASK_ENV: str = field(default_factory=lambda: os.getenv("FLASK_ENV", "development"))
    DEBUG: bool = False
    TESTING: bool = False

    SERVICE_NAME: str = "notification_service"
    SERVICE_HOST: str = field(default_factory=lambda: os.getenv("SERVICE_HOST", "0.0.0.0"))
    SERVICE_PORT: int = field(default_factory=lambda: int(os.getenv("SERVICE_PORT", 5000)))

    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    LOG_FORMAT: str = field(default_factory=lambda: os.getenv("LOG_FORMAT", "json"))

    RABBITMQ_URL: str = field(
        default_factory=lambda: os.getenv(
            "RABBITMQ_URL",
            "amqp://guest:guest@localhost:5672/",
        )
    )
    CELERY_BROKER_URL: str = field(
        default_factory=lambda: os.getenv(
            "CELERY_BROKER_URL",
            os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
        )
    )
    CELERY_RESULT_BACKEND: str = field(
        default_factory=lambda: os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
    )
    CELERY_TASK_DEFAULT_QUEUE: str = field(
        default_factory=lambda: os.getenv("CELERY_TASK_DEFAULT_QUEUE", "notifications.default")
    )
    CELERY_WORKER_CONCURRENCY: int = field(
        default_factory=lambda: int(os.getenv("CELERY_WORKER_CONCURRENCY", 2))
    )

    EMAIL_ENABLED: bool = field(
        default_factory=lambda: os.getenv("EMAIL_ENABLED", "false").lower() == "true"
    )
    WEBHOOKS_ENABLED: bool = field(
        default_factory=lambda: os.getenv("WEBHOOKS_ENABLED", "false").lower() == "true"
    )


@dataclass
class DevelopmentConfig(Config):
    FLASK_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"


@dataclass
class TestingConfig(Config):
    FLASK_ENV: str = "testing"
    TESTING: bool = True
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    CELERY_BROKER_URL: str = "memory://"
    CELERY_RESULT_BACKEND: str = "cache+memory://"


@dataclass
class StagingConfig(Config):
    FLASK_ENV: str = "staging"


@dataclass
class ProductionConfig(Config):
    FLASK_ENV: str = "production"

    def __post_init__(self):
        if not self.CELERY_BROKER_URL:
            raise ValueError("CELERY_BROKER_URL must be configured in production")


def get_config(env: Optional[str] = None) -> Config:
    """Return environment-aware configuration."""

    if env is None:
        env = os.getenv("FLASK_ENV", "development")

    config_map = {
        "development": DevelopmentConfig,
        "dev": DevelopmentConfig,
        "testing": TestingConfig,
        "test": TestingConfig,
        "staging": StagingConfig,
        "production": ProductionConfig,
        "prod": ProductionConfig,
    }
    key = env.lower().strip()
    if key not in config_map:
        raise ValueError(f"Unknown environment: {env}")
    return config_map[key]()
