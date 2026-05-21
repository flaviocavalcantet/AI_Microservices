"""Middleware compatibility exports.

Canonical request context handling lives in ``services.api_service.src.context``.
Canonical error handling lives in ``services.api_service.src.errors``.
"""

from flask import Flask

from services.api_service.src.context import RequestContextManager
from services.api_service.src.errors import register_error_handlers


def inject_correlation_id(app: Flask) -> None:
    """Register request correlation middleware.

    Kept as a compatibility wrapper for older imports.
    """
    RequestContextManager.setup_request_context(app)


__all__ = ["inject_correlation_id", "register_error_handlers"]
