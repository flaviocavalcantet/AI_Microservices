"""Bind Flask request context into shared propagation context vars."""

from flask import Flask, g, request

from shared.shared_http.src.propagation import set_request_context


def register_identity_propagation(app: Flask) -> None:
    """Sync correlation IDs and trace headers after logging middleware runs."""

    @app.before_request
    def _bind_propagation_context():
        auth = request.headers.get("Authorization", "")
        token = None
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()

        set_request_context(
            correlation_id=getattr(g, "correlation_id", None),
            request_id=getattr(g, "request_id", None),
            user_id=getattr(g, "user_id", None),
            bearer_token=getattr(g, "bearer_token", None) or token,
            traceparent=request.headers.get("traceparent"),
        )
