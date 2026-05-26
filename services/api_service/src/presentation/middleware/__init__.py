"""Middleware registration for api-service.

Canonical request-context handling lives in ``services.api_service.src.context``.
Canonical error handling lives in ``services.api_service.src.errors``.

JWT validation is now delegated to ``shared_auth`` via ``jwt_middleware``.
The old ``jwt_auth`` module has been removed.
"""

from flask import Flask

from services.api_service.src.config import Config
from services.api_service.src.context import RequestContextManager
from services.api_service.src.errors import register_error_handlers
from services.api_service.src.presentation.middleware.identity import register_identity_propagation
from services.api_service.src.presentation.middleware.jwt_middleware import register_jwt_auth


def inject_correlation_id(app: Flask) -> None:
    """Register request-correlation middleware.

    Kept as a compatibility shim for older imports.
    """
    RequestContextManager.setup_request_context(app)


def register_auth_middleware(app: Flask, config: Config) -> None:
    """Register correlation, JWT, and propagation middleware."""
    RequestContextManager.setup_request_context(app)
    register_identity_propagation(app)
    register_jwt_auth(
        app,
        secret_key=config.JWT_SECRET_KEY,
        algorithm=config.JWT_ALGORITHM,
        issuer=config.JWT_ISSUER,
        audience=config.JWT_AUDIENCE,
        enabled=config.JWT_AUTH_ENABLED,
        required=config.JWT_AUTH_REQUIRED,
    )


__all__ = [
    "inject_correlation_id",
    "register_auth_middleware",
    "register_error_handlers",
]
