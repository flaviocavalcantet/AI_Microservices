"""Shared HTTP utilities for microservice communication."""

from .propagation import (
    apply_celery_headers,
    apply_inbound_headers,
    build_outbound_headers,
    celery_headers_from_context,
    flask_context_from_g,
    get_correlation_id,
    set_request_context,
)

__all__ = [
    "apply_celery_headers",
    "apply_inbound_headers",
    "build_outbound_headers",
    "celery_headers_from_context",
    "flask_context_from_g",
    "get_correlation_id",
    "set_request_context",
]
