"""Configuration for ai-worker."""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    """Base configuration shared by the HTTP probe and Celery worker."""

    FLASK_ENV: str = field(default_factory=lambda: os.getenv("FLASK_ENV", "development"))
    DEBUG: bool = False
    TESTING: bool = False

    SERVICE_NAME: str = "ai_worker"
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
        default_factory=lambda: os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    )
    CELERY_TASK_DEFAULT_QUEUE: str = field(
        default_factory=lambda: os.getenv("CELERY_TASK_DEFAULT_QUEUE", "ai.default")
    )
    CELERY_WORKER_CONCURRENCY: int = field(
        default_factory=lambda: int(os.getenv("CELERY_WORKER_CONCURRENCY", 4))
    )
    CELERY_TASK_TIME_LIMIT_SECONDS: int = field(
        default_factory=lambda: int(os.getenv("CELERY_TASK_TIME_LIMIT_SECONDS", 3600))
    )

    ENABLE_GPU_DETECTION: bool = field(
        default_factory=lambda: os.getenv("ENABLE_GPU_DETECTION", "true").lower() == "true"
    )
    
    # AI Worker Model Execution
    AI_WORKER_MODEL_PATH: str = field(
        default_factory=lambda: os.getenv("AI_WORKER_MODEL_PATH", "/app/models")
    )
    AI_WORKER_GPU_ENABLED: bool = field(
        default_factory=lambda: os.getenv("AI_WORKER_GPU_ENABLED", "true").lower() == "true"
    )
    AI_WORKER_MAX_WORKERS: int = field(
        default_factory=lambda: int(os.getenv("AI_WORKER_MAX_WORKERS", 4))
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
    LOG_LEVEL: str = "INFO"

    def __post_init__(self):
        if not self.CELERY_BROKER_URL:
            raise ValueError("CELERY_BROKER_URL must be configured in production")


def get_config(env: Optional[str] = None) -> Config:
    """Return the configuration profile for the selected environment."""

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
