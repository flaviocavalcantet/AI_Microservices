"""Request context and correlation ID management."""

from flask import Flask, g

from shared.shared_logging import register_flask_request_logging


class RequestContextManager:
    """Register shared request logging/correlation middleware."""

    @staticmethod
    def setup_request_context(app: Flask) -> None:
        register_flask_request_logging(app, service_name="api_service")


def get_correlation_id() -> str:
    try:
        return g.get("correlation_id", "")
    except RuntimeError:
        return ""


def get_request_id() -> str:
    try:
        return g.get("request_id", "")
    except RuntimeError:
        return ""


def get_user_id() -> str:
    try:
        return g.get("user_id", "")
    except RuntimeError:
        return ""
