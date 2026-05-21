"""Presentation middleware exports for auth-service."""

from flask import Flask

from ...context import RequestContextManager
from ...errors import register_error_handlers


def inject_correlation_id(app: Flask) -> None:
    """Compatibility wrapper for request correlation middleware."""
    RequestContextManager.setup_request_context(app)


__all__ = ["inject_correlation_id", "register_error_handlers"]
