# Base blueprint class with common functionality

import logging
from flask import Blueprint
from services.api_service.src.container import get_container
from services.api_service.src.context import get_correlation_id, get_request_id

logger = logging.getLogger(__name__)


class BaseBlueprint:
    """Base class for all API blueprints
    
    Provides common functionality:
    - Logging with correlation IDs
    - Dependency injection container access
    - Common response formatting
    - Error handling
    
    Example:
        class JobBlueprint(BaseBlueprint):
            def __init__(self):
                super().__init__("jobs", "/api/v1/jobs")
                self.setup_routes()
            
            def setup_routes(self):
                @self.bp.route('', methods=['POST'])
                def create_job():
                    container = self.get_container()
                    use_case = container.resolve('create_job_use_case')
                    # ... implementation
            
            def register(self, app):
                super().register(app)
    """
    
    def __init__(self, name: str, url_prefix: str):
        """Initialize blueprint
        
        Args:
            name: Blueprint name (used internally)
            url_prefix: URL prefix for all routes
        """
        self.bp = Blueprint(
            name,
            __name__,
            url_prefix=url_prefix
        )
        self.logger = logging.getLogger(__name__)
    
    def get_container(self):
        """Get dependency injection container
        
        Returns:
            ServiceContainer instance
        """
        return get_container()
    
    def resolve(self, service_name: str):
        """Resolve service from container
        
        Args:
            service_name: Name of service to resolve
        
        Returns:
            Service instance
        """
        container = self.get_container()
        return container.resolve(service_name)
    
    def get_correlation_context(self):
        """Get current request correlation context
        
        Returns:
            dict with correlation_id, request_id
        """
        return {
            'correlation_id': get_correlation_id(),
            'request_id': get_request_id(),
        }
    
    def register(self, app):
        """Register blueprint with Flask app
        
        Args:
            app: Flask application instance
        """
        app.register_blueprint(self.bp)
        self.logger.debug(f"Registered blueprint: {self.bp.name}")
    
    def log_request(self, method: str, action: str, **extra):
        """Log incoming request
        
        Args:
            method: HTTP method
            action: Action name
            **extra: Additional context
        """
        context = self.get_correlation_context()
        context.update(extra)
        self.logger.info(f"{method} {action}", extra=context)
    
    def log_response(self, status_code: int, action: str, **extra):
        """Log outgoing response
        
        Args:
            status_code: HTTP status code
            action: Action name
            **extra: Additional context
        """
        context = self.get_correlation_context()
        context.update(extra)
        self.logger.info(
            f"Response {status_code} for {action}",
            extra=context
        )
    
    def log_error(self, error: Exception, action: str, **extra):
        """Log error
        
        Args:
            error: Exception instance
            action: Action name
            **extra: Additional context
        """
        context = self.get_correlation_context()
        context.update(extra)
        self.logger.error(
            f"Error in {action}: {str(error)}",
            exc_info=True,
            extra=context
        )
