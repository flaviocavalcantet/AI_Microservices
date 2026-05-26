"""Structured API error handling for auth-service."""

from datetime import datetime
import logging
from typing import Any, Dict

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base API error converted into a JSON response."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_code: str = "API_ERROR",
        details: Dict[str, Any] | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        from flask import g

        payload: Dict[str, Any] = {
            "status": "error",
            "code": self.status_code,
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details,
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        cid = getattr(g, "correlation_id", None) or getattr(g, "request_id", None)
        if cid:
            payload["correlation_id"] = cid
        return payload


class UnauthorizedError(APIError):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, status_code=401, error_code="UNAUTHORIZED")


class ForbiddenError(APIError):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, status_code=403, error_code="FORBIDDEN")


def register_error_handlers(app: Flask) -> None:
    from .domain.exceptions.auth_errors import (
        AuthDomainError,
        ExpiredTokenError,
        InsufficientRolesError,
        InvalidTokenError,
        OAuthCodeExpiredError,
        OAuthProviderError,
        OAuthStateMismatchError,
        RevokedTokenError,
        TokenFamilyCompromisedError,
        UserInactiveError,
        UserNotFoundError,
    )

    @app.errorhandler(OAuthStateMismatchError)
    @app.errorhandler(OAuthCodeExpiredError)
    def handle_oauth_csrf(error: AuthDomainError):
        api_error = APIError(str(error), status_code=400, error_code="OAUTH_STATE_INVALID")
        return jsonify(api_error.to_dict()), api_error.status_code

    @app.errorhandler(OAuthProviderError)
    def handle_oauth_provider(error: OAuthProviderError):
        api_error = APIError(str(error), status_code=502, error_code="OAUTH_PROVIDER_ERROR")
        return jsonify(api_error.to_dict()), api_error.status_code

    @app.errorhandler(InvalidTokenError)
    @app.errorhandler(ExpiredTokenError)
    @app.errorhandler(RevokedTokenError)
    @app.errorhandler(TokenFamilyCompromisedError)
    def handle_token_errors(error: AuthDomainError):
        code = "TOKEN_INVALID"
        status = 401
        if isinstance(error, ExpiredTokenError):
            code = "TOKEN_EXPIRED"
        elif isinstance(error, TokenFamilyCompromisedError):
            code = "TOKEN_FAMILY_COMPROMISED"
            status = 403
        elif isinstance(error, RevokedTokenError):
            code = "TOKEN_REVOKED"
        api_error = APIError(str(error), status_code=status, error_code=code)
        return jsonify(api_error.to_dict()), api_error.status_code

    @app.errorhandler(UserNotFoundError)
    def handle_user_not_found(error: UserNotFoundError):
        api_error = APIError(str(error), status_code=404, error_code="USER_NOT_FOUND")
        return jsonify(api_error.to_dict()), api_error.status_code

    @app.errorhandler(UserInactiveError)
    def handle_user_inactive(error: UserInactiveError):
        api_error = ForbiddenError(str(error))
        return jsonify(api_error.to_dict()), api_error.status_code

    @app.errorhandler(InsufficientRolesError)
    def handle_insufficient_roles(error: InsufficientRolesError):
        api_error = ForbiddenError(str(error))
        return jsonify(api_error.to_dict()), api_error.status_code

    @app.errorhandler(APIError)
    def handle_api_error(error: APIError):
        return jsonify(error.to_dict()), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        api_error = APIError(
            error.description or "HTTP error",
            status_code=error.code,
            error_code=error.name.upper().replace(" ", "_"),
        )
        return jsonify(api_error.to_dict()), error.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        logger.error("Unhandled exception: %s", error, exc_info=True)
        api_error = APIError(
            "Internal server error",
            status_code=500,
            error_code="INTERNAL_ERROR",
        )
        return jsonify(api_error.to_dict()), 500
