# Flask application factory

import os

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
from services.api_service.src.presentation.routes.v1.ai.controller import ai_bp

# Import repositories and use cases
from services.api_service.src.infrastructure.persistence.mongodb.job_repository import MongoJobRepository
from services.api_service.src.infrastructure.external.ai_worker_client import AIWorkerClient
from services.api_service.src.domain.entities.job import Job
from services.api_service.src.application.use_cases.job import (
    CreateJobUseCase,
    ListJobsUseCase,
    GetJobUseCase,
    UpdateJobUseCase,
    CancelJobUseCase,
    DeleteJobUseCase,
)
from services.api_service.src.application.use_cases.ai_processing import (
    SubmitSummarizeUseCase,
    SubmitSentimentUseCase,
    SubmitProfileUseCase,
    SyncWorkerAdapter,
)

# Import MongoDB infrastructure
from shared.shared_infrastructure.src.mongodb import MongoDBConfig

# Import AI engine
from ai_engine.domain.models import AIJob, AIJobType
from ai_engine.infrastructure.container import create_engine

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
    _register_repositories_and_use_cases(container, config)
    
    # Register blueprints
    _register_blueprints(app)
    
    # Setup OpenAPI/Swagger
    if config.SWAGGER_ENABLED:
        _setup_swagger(app, config)
    
    # Setup MongoDB cleanup on app shutdown
    @app.teardown_appcontext
    def cleanup_mongodb(exc=None):
        """Gracefully close MongoDB connection on shutdown."""
        try:
            mongo_manager = container.resolve("mongo_manager")
            if mongo_manager:
                mongo_manager.disconnect()
                logger.info("MongoDB connection closed gracefully")
        except Exception as e:
            logger.warning(f"Error closing MongoDB connection: {e}")
    
    logger.info(
        f"Flask application created successfully",
        extra={"service": config.SERVICE_NAME}
    )
    
    return app


def _register_repositories_and_use_cases(container: ServiceContainer, config: Config) -> None:
    """Register repositories and use cases with the dependency injection container
    
    This function:
    1. Creates and connects to MongoDB
    2. Registers the Job repository
    3. Registers all Job use cases
    4. Registers optional event publisher
    
    Args:
        container: ServiceContainer instance
    
    Raises:
        Exception: If MongoDB connection fails or repository registration fails
    """
    
    if config.TESTING:
        _register_testing_repositories_and_use_cases(container)
        return

    try:
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 1. Create and connect to MongoDB
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        logger.info("Initializing MongoDB connection")
        
        # Create MongoDB config from the loaded app config. Some tests and
        # programmatic callers pass a Config object without mutating os.environ.
        old_mongodb_uri = os.environ.get("MONGODB_URI")
        os.environ["MONGODB_URI"] = config.MONGODB_URI
        try:
            mongo_config = MongoDBConfig.from_env()
        finally:
            if old_mongodb_uri is None:
                os.environ.pop("MONGODB_URI", None)
            else:
                os.environ["MONGODB_URI"] = old_mongodb_uri
        logger.debug(
            "MongoDB config loaded",
            extra={
                "environment": mongo_config.environment,
                "pool_size": f"{mongo_config.resolve_pool_sizes()}",
            }
        )
        
        # Create connection manager
        mongo_manager = mongo_config.create_connection_manager()
        
        # Establish connection (with validation)
        mongo_manager.connect()
        logger.info("MongoDB connection established successfully")
        
        # Get database handle for this service
        db = mongo_manager.get_database("api_service")
        logger.debug(f"Connected to database: {db.name}")
        
        # Register in container for access elsewhere
        container.register_instance("mongo_manager", mongo_manager)
        container.register_instance("database", db)
        logger.debug("Registered mongo_manager and database")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 2. Register Job Repository
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        # Create repository with database handle
        job_repository = MongoJobRepository(database=db)
        container.register_instance("job_repository", job_repository)
        logger.debug("Registered job_repository")
        
        # Register optional event publisher (placeholder)
        # TODO: Implement real event publisher
        container.register_instance("event_publisher", None)
        logger.debug("Registered event_publisher (None/placeholder)")
        
        # Register AI Worker Client for async job execution
        ai_worker_url = container.resolve("config").AI_WORKER_URL
        ai_worker_timeout = container.resolve("config").__dict__.get("AI_WORKER_TIMEOUT_SECONDS", 300)
        ai_worker_poll_interval = container.resolve("config").__dict__.get("AI_WORKER_POLL_INTERVAL_SECONDS", 2)
        
        container.register(
            "ai_worker_client",
            lambda: AIWorkerClient(
                base_url=ai_worker_url,
                timeout_seconds=ai_worker_timeout,
                poll_interval_seconds=ai_worker_poll_interval
            ),
            singleton=True
        )
        logger.debug(f"Registered ai_worker_client: {ai_worker_url}")
        
        # Register Job Use Cases
        container.register(
            "create_job_use_case",
            lambda: CreateJobUseCase(
                repository=container.resolve("job_repository"),
                event_publisher=container.resolve("event_publisher"),
                ai_worker_client=container.resolve("ai_worker_client"),
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
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 3. Create and register AI Engine with use cases
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        logger.info("Initializing AI Engine")
        
        # Create AI engine (synchronous worker with thread pool)
        # It uses the ai_jobs collection in MongoDB
        ai_jobs_collection = db["ai_jobs"]
        ai_worker = create_engine(
            db=db,
            max_workers=4,
            warmup_summarizer=False,  # Set to True to load model on startup
        )
        container.register_instance("ai_worker", ai_worker)
        logger.debug("Registered ai_worker (AIJobWorker)")
        
        # Wrap the worker with the adapter expected by use cases
        ai_worker_adapter = SyncWorkerAdapter(ai_worker)
        container.register_instance("ai_worker_adapter", ai_worker_adapter)
        logger.debug("Registered ai_worker_adapter (SyncWorkerAdapter)")
        
        # Register AI Use Cases
        container.register(
            "submit_summarize_use_case",
            lambda: SubmitSummarizeUseCase(
                worker=container.resolve("ai_worker_adapter"),
            ),
            singleton=True
        )
        logger.debug("Registered submit_summarize_use_case")
        
        container.register(
            "submit_sentiment_use_case",
            lambda: SubmitSentimentUseCase(
                worker=container.resolve("ai_worker_adapter"),
            ),
            singleton=True
        )
        logger.debug("Registered submit_sentiment_use_case")
        
        container.register(
            "submit_profile_use_case",
            lambda: SubmitProfileUseCase(
                worker=container.resolve("ai_worker_adapter"),
            ),
            singleton=True
        )
        logger.debug("Registered submit_profile_use_case")
        
        logger.info("All repositories and use cases registered successfully")
    
    except Exception as e:
        logger.error(f"Error registering repositories and use cases: {e}", exc_info=True)
        raise


def _register_testing_repositories_and_use_cases(container: ServiceContainer) -> None:
    """Register dependency-light in-memory services for unit tests."""
    job_repository = _InMemoryJobRepository()
    container.register_instance("mongo_manager", None)
    container.register_instance("database", None)
    container.register_instance("job_repository", job_repository)
    container.register_instance("event_publisher", None)
    container.register_instance("ai_worker_client", None)

    container.register(
        "create_job_use_case",
        lambda: CreateJobUseCase(repository=job_repository, event_publisher=None, ai_worker_client=None),
        singleton=True,
    )
    container.register(
        "list_jobs_use_case",
        lambda: ListJobsUseCase(repository=job_repository),
        singleton=True,
    )
    container.register(
        "get_job_use_case",
        lambda: GetJobUseCase(repository=job_repository),
        singleton=True,
    )
    container.register(
        "update_job_use_case",
        lambda: UpdateJobUseCase(repository=job_repository, event_publisher=None),
        singleton=True,
    )
    container.register(
        "cancel_job_use_case",
        lambda: CancelJobUseCase(repository=job_repository, event_publisher=None),
        singleton=True,
    )
    container.register(
        "delete_job_use_case",
        lambda: DeleteJobUseCase(repository=job_repository, event_publisher=None),
        singleton=True,
    )

    worker_adapter = _TestingWorkerAdapter()
    container.register_instance("ai_worker_adapter", worker_adapter)
    container.register(
        "submit_summarize_use_case",
        lambda: SubmitSummarizeUseCase(worker=worker_adapter),
        singleton=True,
    )
    container.register(
        "submit_sentiment_use_case",
        lambda: SubmitSentimentUseCase(worker=worker_adapter),
        singleton=True,
    )
    container.register(
        "submit_profile_use_case",
        lambda: SubmitProfileUseCase(worker=worker_adapter),
        singleton=True,
    )


class _InMemoryJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def save(self, job: Job) -> Job:
        self._jobs[job.id] = job
        return job

    def find_by_id(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def find_all(
        self,
        user_id: str | None = None,
        status: str | None = None,
        job_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[Job], int]:
        jobs = list(self._jobs.values())
        if user_id is not None:
            jobs = [job for job in jobs if job.user_id == user_id]
        if status is not None:
            jobs = [job for job in jobs if job.status == status]
        if job_type is not None:
            jobs = [job for job in jobs if job.job_type == job_type]
        reverse = sort_order == "desc"
        jobs.sort(key=lambda job: getattr(job, sort_by), reverse=reverse)
        return jobs[offset : offset + limit], len(jobs)

    def find_by_status(self, status: str, limit: int = 100, offset: int = 0) -> tuple[list[Job], int]:
        return self.find_all(status=status, limit=limit, offset=offset)

    def find_by_user(self, user_id: str, limit: int = 50, offset: int = 0) -> tuple[list[Job], int]:
        return self.find_all(user_id=user_id, limit=limit, offset=offset)

    def update_status(self, job_id: str, status: str) -> Job | None:
        job = self.find_by_id(job_id)
        if job is None:
            return None
        job.status = status
        return self.save(job)

    def delete(self, job_id: str) -> bool:
        return self._jobs.pop(job_id, None) is not None

    def exists(self, job_id: str) -> bool:
        return job_id in self._jobs

    def count(self, user_id: str | None = None, status: str | None = None) -> int:
        _, total = self.find_all(user_id=user_id, status=status)
        return total


class _TestingWorkerAdapter:
    def submit_job_sync(self, job_type: AIJobType, payload: dict, tags: dict) -> AIJob:
        return AIJob(job_type=job_type, payload=payload, tags=tags)

    def get_job_sync(self, job_id: str) -> AIJob:
        return AIJob(job_type=AIJobType.SUMMARIZATION, payload={}, job_id=job_id)


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
    
    # AI Processing API (v1)
    app.register_blueprint(ai_bp)
    logger.debug("Registered ai blueprint")
    
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
