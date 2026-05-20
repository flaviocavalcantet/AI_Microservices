# Structured logging setup

import logging
import json
import sys
from datetime import datetime
from typing import Dict, Any

import flask


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_obj["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        if hasattr(record, "correlation_id"):
            log_obj["correlation_id"] = record.correlation_id
        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            log_obj["user_id"] = record.user_id
        if hasattr(record, "extra"):
            log_obj.update(record.extra)

        return json.dumps(log_obj)


class TextFormatter(logging.Formatter):
    """Format log records as human-readable text"""

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)

        correlation_id = getattr(record, "correlation_id", None)
        request_id = getattr(record, "request_id", None)

        prefix_parts = []
        if correlation_id:
            prefix_parts.append(f"[{correlation_id}]")
        if request_id:
            prefix_parts.append(f"[{request_id}]")

        prefix = " ".join(prefix_parts)
        if prefix:
            msg = f"{prefix} {msg}"

        return msg


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure structured logging for the application"""

    level = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if log_format.lower() == "json":
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    logging.getLogger("flask").setLevel(level)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.LoggerAdapter:
    """Get logger with support for correlation IDs"""

    logger = logging.getLogger(name)

    class ContextAwareAdapter(logging.LoggerAdapter):
        def process(self, msg: str, kwargs: Dict[str, Any]):
            try:
                correlation_id = flask.g.get("correlation_id")
                request_id = flask.g.get("request_id")
                user_id = flask.g.get("user_id")

                if "extra" not in kwargs:
                    kwargs["extra"] = {}

                if correlation_id:
                    kwargs["extra"]["correlation_id"] = correlation_id
                if request_id:
                    kwargs["extra"]["request_id"] = request_id
                if user_id:
                    kwargs["extra"]["user_id"] = user_id

            except (RuntimeError, AttributeError):
                pass

            return msg, kwargs

    return ContextAwareAdapter(logger, {})