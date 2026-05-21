"""api-service logging facade."""

import os

from shared.shared_logging import JSONFormatter, TextFormatter
from shared.shared_logging import get_logger as _get_logger
from shared.shared_logging import setup_logging as _setup_logging

SERVICE_NAME = "api_service"


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    _setup_logging(
        log_level=log_level,
        log_format=log_format,
        service_name=SERVICE_NAME,
        environment=os.getenv("FLASK_ENV"),
        noisy_loggers=("werkzeug", "pymongo", "kombu"),
    )


def get_logger(name: str):
    return _get_logger(name, service_name=SERVICE_NAME)


__all__ = ["JSONFormatter", "TextFormatter", "get_logger", "setup_logging"]
