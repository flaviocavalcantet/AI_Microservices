"""Request context and correlation ID support."""

from flask import Flask, g, request

from shared.shared_logging import register_flask_request_logging


class RequestContextManager:
    """Register shared request logging/correlation middleware."""

    @staticmethod
    def setup_request_context(app: Flask) -> None:
        register_flask_request_logging(app, service_name="auth_service")

        @app.before_request
        def parse_roles():
            g.roles = _parse_roles_header(request.headers.get("X-Roles"))


def _parse_roles_header(value: str | None) -> list[str]:
    if not value:
        return []
    return [role.strip() for role in value.split(",") if role.strip()]
