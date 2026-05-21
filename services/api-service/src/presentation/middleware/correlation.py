# Correlation ID injection middleware

import logging
from functools import wraps
from uuid import uuid4
from flask import request, g

logger = logging.getLogger(__name__)


def inject_correlation_id(app):
    """Register correlation ID injection before/after request handlers
    
    Ensures all requests have correlation IDs for tracing across microservices.
    
    Args:
        app: Flask application instance
    """
    
    @app.before_request
    def before_request_correlation():
        """Before request: inject or generate correlation ID"""
        
        # Try to get correlation ID from request headers
        correlation_id = request.headers.get('X-Correlation-ID')
        
        if not correlation_id:
            # Generate new correlation ID
            correlation_id = str(uuid4())
            logger.debug(f"Generated new correlation ID: {correlation_id}")
        
        # Store in Flask g (request-scoped)
        g.correlation_id = correlation_id
        
        # Also get/generate request ID (unique per request)
        request_id = request.headers.get('X-Request-ID', str(uuid4()))
        g.request_id = request_id
        
        # Extract user ID if present (from auth token, etc.)
        # This will be implemented with authentication middleware
        g.user_id = request.headers.get('X-User-ID')
    
    @app.after_request
    def after_request_correlation(response):
        """After request: add correlation IDs to response headers"""
        
        response.headers['X-Correlation-ID'] = g.get('correlation_id', 'N/A')
        response.headers['X-Request-ID'] = g.get('request_id', 'N/A')
        
        return response


def get_correlation_context():
    """Get current request correlation context
    
    Returns:
        dict with correlation_id, request_id, user_id
    """
    return {
        'correlation_id': g.get('correlation_id'),
        'request_id': g.get('request_id'),
        'user_id': g.get('user_id'),
    }
