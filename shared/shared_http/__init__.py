"""Shared HTTP client and context propagation for microservices."""

from .src.propagation import (
    apply_celery_headers,
    apply_inbound_headers,
    build_outbound_headers,
    celery_headers_from_context,
    flask_context_from_g,
    get_bearer_token,
    get_correlation_id,
    set_request_context,
)
from .src.client import ServiceHttpClient

__all__ = [
    "ServiceHttpClient",
    "apply_celery_headers",
    "apply_inbound_headers",
    "build_outbound_headers",
    "celery_headers_from_context",
    "flask_context_from_g",
    "get_bearer_token",
    "get_correlation_id",
    "set_request_context",
]
