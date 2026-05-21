# Error handling middleware

import logging
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException
from services.api_service.src.errors import APIError
from services.api_service.src.context import get_correlation_id

logger = logging.getLogger(__name__)


def register_error_handlers(app: Flask) -> None:
    """Register error handlers for consistent error responses
    
    Handles:
    - APIError (custom application errors)
    - HTTPException (Flask/Werkzeug errors)
    - Unexpected exceptions (500 errors)
    
    Args:
        app: Flask application instance
    """
    
    @app.errorhandler(APIError)
    def handle_api_error(error: APIError):
        """Handle custom API errors with consistent response format"""
        
        logger.warning(
            f"API Error: {error.error_code}",
            extra={
                "error_code": error.error_code,
                "status_code": error.status_code,
                "message": error.message,
            }
        )
        
        response = error.to_dict()
        response['correlation_id'] = get_correlation_id()
        response['timestamp'] = __import__('datetime').datetime.utcnow().isoformat() + 'Z'
        
        return jsonify(response), error.status_code
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        """Handle Flask/Werkzeug HTTP exceptions"""
        
        logger.warning(
            f"HTTP Exception: {error.code}",
            extra={
                "code": error.code,
                "description": error.description,
            }
        )
        
        response = {
            "status": "error",
            "error": {
                "code": error.code,
                "message": error.description or str(error),
            },
            "correlation_id": get_correlation_id(),
            "timestamp": __import__('datetime').datetime.utcnow().isoformat() + 'Z',
        }
        
        return jsonify(response), error.code
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        """Handle unexpected exceptions (500 errors)"""
        
        logger.error(
            f"Unexpected error: {str(error)}",
            exc_info=True,
            extra={
                "error_type": type(error).__name__,
                "error_message": str(error),
            }
        )
        
        response = {
            "status": "error",
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
            },
            "correlation_id": get_correlation_id(),
            "timestamp": __import__('datetime').datetime.utcnow().isoformat() + 'Z',
        }
        
        return jsonify(response), 500
    
    @app.errorhandler(404)
    def handle_not_found(error):
        """Handle 404 Not Found"""
        
        logger.debug(f"Not found: {error}")
        
        response = {
            "status": "error",
            "error": {
                "code": "NOT_FOUND",
                "message": "Resource not found",
            },
            "correlation_id": get_correlation_id(),
            "timestamp": __import__('datetime').datetime.utcnow().isoformat() + 'Z',
        }
        
        return jsonify(response), 404
    
    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        """Handle 405 Method Not Allowed"""
        
        response = {
            "status": "error",
            "error": {
                "code": "METHOD_NOT_ALLOWED",
                "message": "Method not allowed",
            },
            "correlation_id": get_correlation_id(),
            "timestamp": __import__('datetime').datetime.utcnow().isoformat() + 'Z',
        }
        
        return jsonify(response), 405
