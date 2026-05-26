# Flask application factory

from flask import Flask
from flask_cors import CORS
from flasgger import Swagger

from services.api_service.src.config import Config, get_config
from services.api_service.src.logger import setup_logging, get_logger
from services.api_service.src.container import ServiceContainer, init_container
from services.api_service.src.errors import register_error_handlers
from services.api_service.src.presentation.middleware import register_auth_middleware
from services.api_service.src.presentation.routes.health import health_bp
from services.api_service.src.presentation.routes.v1.jobs.controller import jobs_bp

# Import repositories and use cases
from services.api_service.src.infrastructure.persistence.mongodb.job_repository import MongoJobRepository
from services.api_service.src.application.use_cases.job import (
    CreateJobUseCase,
    ListJobsUseCase,
    GetJobUseCase,
    UpdateJobUseCase,
    CancelJobUseCase,
    DeleteJobUseCase,
)

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
    
    # Correlation IDs, JWT auth, and propagation context
    register_auth_middleware(app, config)

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
    
    # Register repositories and use cases
    _register_repositories_and_use_cases(container)
    
    # Register blueprints
    _register_blueprints(app)
    
    # Setup OpenAPI/Swagger
    if config.SWAGGER_ENABLED:
        _setup_swagger(app, config)
    
    logger.info(
        f"Flask application created successfully",
        extra={"service": config.SERVICE_NAME}
    )
    
    return app


def _register_repositories_and_use_cases(container: ServiceContainer) -> None:
    """Register repositories and use cases with the dependency injection container
    
    This function:
    1. Registers the Job repository
    2. Registers all Job use cases
    3. Registers optional event publisher
    
    Args:
        container: ServiceContainer instance
    """
    
    try:
        # Register Job Repository
        # TODO: Inject MongoDB client once available
        job_repository = MongoJobRepository(db_client=None)
        container.register_instance("job_repository", job_repository)
        logger.debug("Registered job_repository")
        
        # Register optional event publisher (placeholder)
        # TODO: Implement real event publisher
        container.register_instance("event_publisher", None)
        
        # Register Job Use Cases
        container.register(
            "create_job_use_case",
            lambda: CreateJobUseCase(
                repository=container.resolve("job_repository"),
                event_publisher=container.resolve("event_publisher"),
            ),
            singleton=True
        )
        logger.debug("Registered create_job_use_case")
        
        container.register(
            "list_jobs_use_case",
            lambda: ListJobsUseCase(
                repository=container.resolve("job_repository"),
            ),
            singleton=True
        )
        logger.debug("Registered list_jobs_use_case")
        
        container.register(
            "get_job_use_case",
            lambda: GetJobUseCase(
                repository=container.resolve("job_repository"),
            ),
            singleton=True
        )
        logger.debug("Registered get_job_use_case")
        
        container.register(
            "update_job_use_case",
            lambda: UpdateJobUseCase(
                repository=container.resolve("job_repository"),
                event_publisher=container.resolve("event_publisher"),
            ),
            singleton=True
        )
        logger.debug("Registered update_job_use_case")
        
        container.register(
            "cancel_job_use_case",
            lambda: CancelJobUseCase(
                repository=container.resolve("job_repository"),
                event_publisher=container.resolve("event_publisher"),
            ),
            singleton=True
        )
        logger.debug("Registered cancel_job_use_case")
        
        container.register(
            "delete_job_use_case",
            lambda: DeleteJobUseCase(
                repository=container.resolve("job_repository"),
                event_publisher=container.resolve("event_publisher"),
            ),
            singleton=True
        )
        logger.debug("Registered delete_job_use_case")
        
        logger.info("All repositories and use cases registered successfully")
    
    except Exception as e:
        logger.error(f"Error registering repositories and use cases: {e}", exc_info=True)
        raise


def _register_blueprints(app: Flask) -> None:
    """Register all blueprints with Flask app
    
    Blueprints are modular route handlers.
    Register them here in a single place for easy management.
    
    Args:
        app: Flask application instance
    """
    
    # Health check endpoints
    app.register_blueprint(health_bp)
    logger.debug("Registered health blueprint")
    
    # Jobs API (v1)
    app.register_blueprint(jobs_bp)
    logger.debug("Registered jobs blueprint")
    
    # TODO: Register other blueprints here as they are implemented
    # from services.api_service.src.presentation.routes.v1.users.controller import users_bp
    # app.register_blueprint(users_bp)
    # logger.debug("Registered users blueprint")
    #
    # from services.api_service.src.presentation.routes.v1.requests.controller import requests_bp
    # app.register_blueprint(requests_bp)
    # logger.debug("Registered requests blueprint")
    # app.register_blueprint(request_bp)


def _setup_swagger(app: Flask, config: Config) -> None:
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

    spec_key = "openapi" if config.OPENAPI_VERSION.startswith("3") else "swagger"
    swagger_template = {
        spec_key: config.OPENAPI_VERSION,
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
