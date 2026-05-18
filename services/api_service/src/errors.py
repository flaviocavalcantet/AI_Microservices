# Error handling middleware and utilities

import logging
from typing import Tuple, Dict, Any
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for API errors
    
    Automatically converted to HTTP response by error handler
    """
    
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_code: str = "INTERNAL_ERROR",
        details: Dict[str, Any] = None
    ):
        """Initialize API error
        
        Args:
            message: Human-readable error message
            status_code: HTTP status code
            error_code: Machine-readable error code
            details: Additional error details
        """
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to JSON-serializable dict"""
        return {
            "status": "error",
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details
            }
        }


class ValidationError(APIError):
    """Validation failed"""
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(message, status_code=400, error_code="VALIDATION_ERROR", details=details)


class UnauthorizedError(APIError):
    """Authentication required"""
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, status_code=401, error_code="UNAUTHORIZED")


class ForbiddenError(APIError):
    """Insufficient permissions"""
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, status_code=403, error_code="FORBIDDEN")


class NotFoundError(APIError):
    """Resource not found"""
    def __init__(self, resource: str):
        super().__init__(f"{resource} not found", status_code=404, error_code="NOT_FOUND")


class ConflictError(APIError):
    """Resource already exists"""
    def __init__(self, message: str):
        super().__init__(message, status_code=409, error_code="CONFLICT")


class RateLimitError(APIError):
    """Too many requests"""
    def __init__(self, message: str = "Too many requests"):
        super().__init__(message, status_code=429, error_code="RATE_LIMITED")


class ServiceUnavailableError(APIError):
    """Service temporarily unavailable"""
    def __init__(self, service: str):
        message = f"{service} is temporarily unavailable"
        super().__init__(message, status_code=503, error_code="SERVICE_UNAVAILABLE")


def register_error_handlers(app: Flask) -> None:
    """Register error handlers for the Flask application
    
    Handles:
    - APIError subclasses
    - HTTPException (Flask/Werkzeug errors)
    - Unexpected exceptions
    
    Args:
        app: Flask application instance
    """
    
    @app.errorhandler(APIError)
    def handle_api_error(error: APIError) -> Tuple[Dict, int]:
        """Handle custom API errors"""
        logger.warning(
            f"API Error: {error.error_code} - {error.message}",
            extra={
                "error_code": error.error_code,
                "status_code": error.status_code,
            }
        )
        return jsonify(error.to_dict()), error.status_code
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException) -> Tuple[Dict, int]:
        """Handle Flask/Werkzeug HTTP exceptions"""
        response = {
            "status": "error",
            "error": {
                "code": error.code,
                "message": error.description or str(error),
            }
        }
        return jsonify(response), error.code
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception) -> Tuple[Dict, int]:
        """Handle unexpected errors"""
        logger.error(
            f"Unexpected error: {str(error)}",
            exc_info=True
        )
        
        response = {
            "status": "error",
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
            }
        }
        return jsonify(response), 500
    
    @app.errorhandler(404)
    def handle_not_found(error) -> Tuple[Dict, int]:
        """Handle 404 Not Found"""
        response = {
            "status": "error",
            "error": {
                "code": "NOT_FOUND",
                "message": "Endpoint not found",
            }
        }
        return jsonify(response), 404
    
    @app.errorhandler(405)
    def handle_method_not_allowed(error) -> Tuple[Dict, int]:
        """Handle 405 Method Not Allowed"""
        response = {
            "status": "error",
            "error": {
                "code": "METHOD_NOT_ALLOWED",
                "message": "Method not allowed for this endpoint",
            }
        }
        return jsonify(response), 405
