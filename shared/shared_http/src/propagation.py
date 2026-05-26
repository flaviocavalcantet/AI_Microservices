"""HTTP context propagation helpers for microservice calls.

Framework-independent — safe to use from Flask, Celery tasks, or scripts.
Pair with SPIFFE/mTLS at the transport layer (see docs/IDENTITY_PROPAGATION.md).
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Dict, Mapping, MutableMapping, Optional

# Request-scoped context (set by middleware or task wrapper)
_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_user_id: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
_traceparent: ContextVar[Optional[str]] = ContextVar("traceparent", default=None)
_bearer_token: ContextVar[Optional[str]] = ContextVar("bearer_token", default=None)


def set_request_context(
    *,
    correlation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    traceparent: Optional[str] = None,
    bearer_token: Optional[str] = None,
) -> None:
    """Bind propagation values for the current execution context."""
    if correlation_id is not None:
        _correlation_id.set(correlation_id)
    if request_id is not None:
        _request_id.set(request_id)
    if user_id is not None:
        _user_id.set(user_id)
    if traceparent is not None:
        _traceparent.set(traceparent)
    if bearer_token is not None:
        _bearer_token.set(bearer_token)


def get_correlation_id() -> str:
    return _correlation_id.get() or _request_id.get() or str(uuid.uuid4())


def get_request_id() -> str:
    return _request_id.get() or str(uuid.uuid4())


def get_user_id() -> Optional[str]:
    return _user_id.get()


def get_traceparent() -> Optional[str]:
    return _traceparent.get()


def get_bearer_token() -> Optional[str]:
    return _bearer_token.get()


def sync_from_flask_g() -> None:
    """Alias for :func:`flask_context_from_g`."""
    flask_context_from_g()


def build_outbound_headers(
    extra: Optional[Mapping[str, str]] = None,
    *,
    include_auth: bool = True,
    new_request_id: bool = True,
) -> Dict[str, str]:
    """Build headers for service-to-service HTTP calls.

    Always propagates correlation ID. Generates a new request ID per hop by default.
    Includes Authorization only when a bearer token is in context.
    """
    headers: Dict[str, str] = {
        "X-Correlation-ID": get_correlation_id(),
        "X-Request-ID": str(uuid.uuid4()) if new_request_id else get_request_id(),
    }

    traceparent = get_traceparent()
    if traceparent:
        headers["traceparent"] = traceparent

    user_id = get_user_id()
    if user_id:
        # Informational — receivers must validate JWT for auth decisions
        headers["X-User-ID"] = user_id

    if include_auth:
        token = get_bearer_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

    if extra:
        headers.update(dict(extra))

    return headers


def apply_inbound_headers(headers: Mapping[str, str]) -> None:
    """Extract propagation headers from an inbound HTTP request."""
    correlation = headers.get("X-Correlation-ID") or headers.get("x-correlation-id")
    request = headers.get("X-Request-ID") or headers.get("x-request-id")
    trace = headers.get("traceparent")
    auth = headers.get("Authorization") or headers.get("authorization") or ""
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else None

    set_request_context(
        correlation_id=correlation or request,
        request_id=request or str(uuid.uuid4()),
        traceparent=trace,
        bearer_token=token,
    )


def flask_context_from_g() -> None:
    """Copy Flask ``g`` attributes into context vars (call after JWT middleware)."""
    try:
        from flask import g
    except ImportError:
        return

    set_request_context(
        correlation_id=getattr(g, "correlation_id", None),
        request_id=getattr(g, "request_id", None),
        user_id=getattr(g, "user_id", None),
    )


def celery_headers_from_context() -> Dict[str, str]:
    """Headers dict for Celery ``apply_async(headers=...)``."""
    out: Dict[str, str] = {
        "correlation_id": get_correlation_id(),
        "request_id": get_request_id(),
    }
    if get_user_id():
        out["user_id"] = get_user_id()  # type: ignore[assignment]
    if get_traceparent():
        out["traceparent"] = get_traceparent()  # type: ignore[assignment]
    return out


def apply_celery_headers(headers: Optional[MutableMapping[str, str]]) -> None:
    """Restore context from Celery task headers."""
    if not headers:
        return
    set_request_context(
        correlation_id=headers.get("correlation_id"),
        request_id=headers.get("request_id"),
        user_id=headers.get("user_id"),
        traceparent=headers.get("traceparent"),
    )
