"""Production-grade structured logging helpers.

This module is intentionally framework-light. Flask integration is optional and
Celery/worker processes can use the same JSON formatter and logger adapter.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable

try:
    from flask import Flask, g, request
except ImportError:  # pragma: no cover - worker-only environments may omit Flask
    Flask = None
    g = None
    request = None


RESERVED_LOG_RECORD_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "message",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}

SENSITIVE_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "cookie",
    "jwt",
    "password",
    "refresh_token",
    "secret",
    "set_cookie",
    "token",
}


def _utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _is_sensitive_key(key) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item) for item in value)
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(sensitive in normalized for sensitive in SENSITIVE_KEYS)


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for aggregation and tracing."""

    def __init__(self, service_name: str | None = None, environment: str | None = None):
        super().__init__()
        self.service_name = service_name
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": _utc_now(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if self.service_name:
            payload["service"] = self.service_name
        if self.environment:
            payload["environment"] = self.environment

        if record.exc_info:
            payload["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        for key, value in record.__dict__.items():
            if key not in RESERVED_LOG_RECORD_ATTRS and key not in payload:
                payload[key] = "[REDACTED]" if _is_sensitive_key(key) else _redact(value)

        return json.dumps(payload, default=str, separators=(",", ":"))


class TextFormatter(logging.Formatter):
    """Human-readable formatter for local debugging."""

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        correlation_id = getattr(record, "correlation_id", None)
        request_id = getattr(record, "request_id", None)
        prefix = " ".join(item for item in [correlation_id, request_id] if item)
        return f"[{prefix}] {message}" if prefix else message


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    service_name: str | None = None,
    environment: str | None = None,
    noisy_loggers: Iterable[str] | None = None,
) -> None:
    """Configure root logging for service processes."""

    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    if log_format.lower() == "json":
        handler.setFormatter(JSONFormatter(service_name=service_name, environment=environment))
    else:
        handler.setFormatter(
            TextFormatter("%(asctime)s %(name)s %(levelname)s %(message)s")
        )

    root_logger.addHandler(handler)

    for logger_name in noisy_loggers or ("werkzeug", "pymongo", "kombu"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def get_logger(name: str, service_name: str | None = None) -> logging.LoggerAdapter:
    """Return a logger adapter that injects request context when available."""

    class ContextAwareAdapter(logging.LoggerAdapter):
        def process(self, msg: str, kwargs: Dict[str, Any]):
            kwargs.setdefault("extra", {})
            if service_name:
                kwargs["extra"].setdefault("service", service_name)

            if g is not None:
                try:
                    for attr in ("correlation_id", "request_id", "user_id"):
                        value = g.get(attr)
                        if value:
                            kwargs["extra"].setdefault(attr, value)
                except RuntimeError:
                    pass

            return msg, kwargs

    return ContextAwareAdapter(logging.getLogger(name), {})


def register_flask_request_logging(app: Flask, service_name: str) -> None:
    """Register request, response, and error logging middleware for Flask."""

    logger = get_logger(f"{service_name}.http", service_name=service_name)

    @app.before_request
    def _before_request():
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        correlation_id = request.headers.get("X-Correlation-ID", request_id)

        g.request_id = request_id
        g.correlation_id = correlation_id
        g.user_id = request.headers.get("X-User-ID")
        g.request_started_at = time.perf_counter()
        g.request_metadata = {
            "method": request.method,
            "path": request.path,
            "remote_addr": request.headers.get("X-Forwarded-For", request.remote_addr),
            "user_agent": request.headers.get("User-Agent", ""),
        }

        logger.info(
            "http.request.started",
            extra={
                "event": "http.request.started",
                "http_method": request.method,
                "http_path": request.path,
                "http_query": request.query_string.decode("utf-8", errors="ignore"),
                "remote_addr": g.request_metadata["remote_addr"],
                "user_agent": g.request_metadata["user_agent"],
            },
        )

    @app.after_request
    def _after_request(response):
        duration_ms = _duration_ms()
        response.headers["X-Request-ID"] = g.get("request_id", "")
        response.headers["X-Correlation-ID"] = g.get("correlation_id", "")

        status_code = response.status_code
        level = logging.ERROR if status_code >= 500 else logging.WARNING if status_code >= 400 else logging.INFO
        logger.log(
            level,
            "http.response.completed",
            extra={
                "event": "http.response.completed",
                "http_method": request.method,
                "http_path": request.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "content_length": response.calculate_content_length(),
            },
        )
        return response

    @app.teardown_request
    def _teardown_request(exception):
        if exception is not None:
            logger.error(
                "http.request.error",
                exc_info=True,
                extra={
                    "event": "http.request.error",
                    "http_method": request.method,
                    "http_path": request.path,
                    "duration_ms": _duration_ms(),
                    "exception_type": type(exception).__name__,
                },
            )


def _duration_ms() -> float | None:
    if g is None:
        return None
    try:
        started_at = g.get("request_started_at")
    except RuntimeError:
        return None
    if started_at is None:
        return None
    return round((time.perf_counter() - started_at) * 1000, 3)
