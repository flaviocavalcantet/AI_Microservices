# Request context and correlation ID management

import uuid
import logging
from flask import Flask, request, g

logger = logging.getLogger(__name__)


class RequestContextManager:
    """Manage request context including correlation IDs
    
    Provides:
    - Unique request ID per request
    - Correlation ID for tracing across services
    - User ID (if authenticated)
    - Request metadata (IP, user agent, etc.)
    """
    
    @staticmethod
    def setup_request_context(app: Flask) -> None:
        """Register Flask request handlers for context management
        
        Args:
            app: Flask application instance
        """
        
        @app.before_request
        def before_request():
            """Setup request context before handling request"""
            
            # Generate or retrieve request ID
            request_id = request.headers.get(
                "X-Request-ID",
                str(uuid.uuid4())
            )
            g.request_id = request_id
            
            # Get or create correlation ID (for tracing)
            correlation_id = request.headers.get(
                "X-Correlation-ID",
                request_id  # Use request ID if no correlation ID provided
            )
            g.correlation_id = correlation_id
            
            # Extract user ID from authorization context (if available)
            g.user_id = request.headers.get("X-User-ID")
            
            # Store request metadata
            g.request_metadata = {
                "method": request.method,
                "path": request.path,
                "ip_address": request.remote_addr,
                "user_agent": request.headers.get("User-Agent", ""),
            }
            
            logger.debug(
                f"Request started",
                extra={
                    "correlation_id": correlation_id,
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.path,
                }
            )
        
        @app.after_request
        def after_request(response):
            """Add correlation IDs to response headers"""
            
            # Add IDs to response for client tracking
            response.headers["X-Request-ID"] = g.get("request_id", "")
            response.headers["X-Correlation-ID"] = g.get("correlation_id", "")
            
            return response
        
        @app.teardown_request
        def teardown_request(exception):
            """Cleanup after request"""
            
            if exception:
                logger.error(
                    f"Request error: {exception}",
                    extra={
                        "correlation_id": g.get("correlation_id"),
                        "request_id": g.get("request_id"),
                    },
                    exc_info=True
                )
            else:
                logger.debug(
                    f"Request completed",
                    extra={
                        "correlation_id": g.get("correlation_id"),
                        "request_id": g.get("request_id"),
                    }
                )


def get_correlation_id() -> str:
    """Get current request correlation ID
    
    Returns:
        Correlation ID for tracing requests
    
    Raises:
        RuntimeError: If called outside request context
    """
    try:
        return g.get("correlation_id", "")
    except RuntimeError:
        return ""


def get_request_id() -> str:
    """Get current request ID
    
    Returns:
        Unique ID for this request
    
    Raises:
        RuntimeError: If called outside request context
    """
    try:
        return g.get("request_id", "")
    except RuntimeError:
        return ""


def get_user_id() -> str:
    """Get current user ID from context
    
    Returns:
        User ID if authenticated, empty string otherwise
    """
    try:
        return g.get("user_id", "")
    except RuntimeError:
        return ""
