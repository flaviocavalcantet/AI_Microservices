# Flask application factory

import logging
from flask import Flask
from flask_cors import CORS
from flasgger import Swagger

from services.api_service.src.config import Config, get_config
from services.api_service.src.logger import setup_logging, get_logger
from services.api_service.src.container import ServiceContainer, init_container
from services.api_service.src.context import RequestContextManager
from services.api_service.src.errors import register_error_handlers
from services.api_service.src.presentation.routes.health import health_bp

logger = get_logger(__name__)


def create_app(config: Config = None, container: ServiceContainer = None) -> Flask:
    """Application factory - creates and configures Flask app
    
    This function:
    1. Creates Flask application instance
    2. Loads configuration
    3. Setup logging
    4. Setup dependency injection container
    5. Register middleware and error handlers
    6. Register blueprints
    7. Configure OpenAPI/Swagger
    
    Args:
        config: Configuration object (if None, loads from environment)
        container: Service container (if None, creates new one)
    
    Returns:
        Configured Flask application instance
    
    Example:
        >>> app = create_app()
        >>> app.run()
        
        >>> # With custom config
        >>> config = ProductionConfig()
        >>> app = create_app(config=config)
    """
    
    # Load configuration
    if config is None:
        config = get_config()
    
    # Create Flask app
    app = Flask(
        import_name=__name__,
        instance_relative_config=False
    )
    
    # Apply configuration
    app.config.from_object(config)
    
    # Setup logging
    setup_logging(
        log_level=config.LOG_LEVEL,
        log_format=config.LOG_FORMAT
    )
    
    logger.info(
        f"Creating Flask application",
        extra={
            "environment": config.FLASK_ENV,
            "service": config.SERVICE_NAME,
            "debug": config.DEBUG,
        }
    )
    
    # Setup dependency injection container
    if container is None:
        container = ServiceContainer()
    
    # Register configuration in container
    container.register_instance("config", config)
    
    # Set global container
    init_container(container)
    
    # Setup request context (correlation IDs, request IDs)
    RequestContextManager.setup_request_context(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Setup CORS
    if config.CORS_ALLOWED_ORIGINS:
        CORS(
            app,
            resources={r"/api/*": {"origins": config.CORS_ALLOWED_ORIGINS}},
            supports_credentials=True,
            allow_headers=["Content-Type", "Authorization", "X-Correlation-ID", "X-Request-ID"],
            expose_headers=["X-Correlation-ID", "X-Request-ID"],
        )
        logger.debug(f"CORS configured for: {config.CORS_ALLOWED_ORIGINS}")
    
    # Register blueprints
    _register_blueprints(app)
    
    # Setup OpenAPI/Swagger
    if config.SWAGGER_ENABLED:
        _setup_swagger(app)
    
    logger.info(
        f"Flask application created successfully",
        extra={"service": config.SERVICE_NAME}
    )
    
    return app


def _register_blueprints(app: Flask) -> None:
    """Register all blueprints with Flask app
    
    Blueprints are modular route handlers.
    Register them here in a single place for easy management.
    
    Args:
        app: Flask application instance
    """
    
    # Health check endpoints
    app.register_blueprint(health_bp)
    logger.debug("Registered health check blueprint")
    
    # TODO: Register other blueprints here as they are implemented
    # app.register_blueprint(user_bp)
    # app.register_blueprint(job_bp)
    # app.register_blueprint(request_bp)


def _setup_swagger(app: Flask) -> None:
    """Setup OpenAPI/Swagger documentation"""

    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": "apispec",
                "route": "/apispec.json",
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/apidocs/",
    }

    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "API Service",
            "description": "AI Microservices API",
            "version": "1.0.0",
            "contact": {
                "name": "API Support",
                "email": "api-support@example.com",
            },
        },
    }

    Swagger(
        app,
        config=swagger_config,
        template=swagger_template,
    )

    logger.debug("Swagger/OpenAPI documentation configured")

def create_app_with_context(config: Config = None, container: ServiceContainer = None):
    """Create app and return with application context
    
    Useful for testing and CLI commands that need app context.
    
    Example:
        >>> with create_app_with_context() as app:
        ...     # Use app here
        ...     pass
    """
    app = create_app(config=config, container=container)
    return app.app_context()
