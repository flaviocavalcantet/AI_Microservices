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
        return {
            "status": "error",
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details,
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }


class UnauthorizedError(APIError):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, status_code=401, error_code="UNAUTHORIZED")


class ForbiddenError(APIError):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, status_code=403, error_code="FORBIDDEN")


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(APIError)
    def handle_api_error(error: APIError):
        return jsonify(error.to_dict()), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        payload = {
            "status": "error",
            "error": {
                "code": error.code,
                "message": error.description,
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        return jsonify(payload), error.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        logger.error("Unhandled exception: %s", error, exc_info=True)
        payload = {
            "status": "error",
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        return jsonify(payload), 500
