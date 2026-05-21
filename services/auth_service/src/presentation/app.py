# Flask application factory

from flask import Flask
from flask_cors import CORS
from flasgger import Swagger

from ..config import Config, get_config
from ..container import ServiceContainer, init_container
from ..context import RequestContextManager
from ..errors import register_error_handlers
from ..infrastructure.security.authorization import RoleBasedAuthorizationPolicy
from ..infrastructure.security.jwt_service import JwtTokenService
from ..infrastructure.security.oauth_registry import OAuthProviderRegistry
from ..logger import setup_logging, get_logger
from .routes.health import health_bp

logger = get_logger(__name__)


def create_app(config: Config = None, container: ServiceContainer = None) -> Flask:
    """Application factory - creates and configures Flask app"""

    if config is None:
        config = get_config()

    app = Flask(
        import_name=__name__,
        instance_relative_config=False,
    )

    app.config.from_object(config)

    setup_logging(
        log_level=config.LOG_LEVEL,
        log_format=config.LOG_FORMAT,
    )

    logger.info(
        "Creating Flask application",
        extra={
            "environment": config.FLASK_ENV,
            "service": config.SERVICE_NAME,
            "debug": config.DEBUG,
        },
    )

    if container is None:
        container = ServiceContainer()

    container.register_instance("config", config)
    init_container(container)

    RequestContextManager.setup_request_context(app)
    register_error_handlers(app)
    _register_auth_infrastructure(container, config)

    # Setup CORS
    if config.CORS_ALLOWED_ORIGINS:
        CORS(
            app,
            resources={r"/api/*": {"origins": config.CORS_ALLOWED_ORIGINS}},
            supports_credentials=True,
            allow_headers=[
                "Content-Type",
                "Authorization",
                "X-Correlation-ID",
                "X-Request-ID",
            ],
            expose_headers=["X-Correlation-ID", "X-Request-ID"],
        )

    # Register blueprints
    _register_blueprints(app)

    # Setup Swagger
    if config.SWAGGER_ENABLED:
        _setup_swagger(app, config)

    logger.info(
        "Flask application created successfully",
        extra={"service": config.SERVICE_NAME},
    )

    return app


def _register_auth_infrastructure(container: ServiceContainer, config: Config) -> None:
    """Register auth-ready infrastructure without enabling auth workflows."""

    container.register(
        "token_service",
        lambda: JwtTokenService(
            secret_key=config.JWT_SECRET_KEY,
            algorithm=config.JWT_ALGORITHM,
            issuer=config.JWT_ISSUER,
            audience=config.JWT_AUDIENCE,
        ),
        singleton=True,
    )
    container.register("oauth_provider_registry", OAuthProviderRegistry, singleton=True)
    container.register("authorization_policy", RoleBasedAuthorizationPolicy, singleton=True)
    logger.debug("Registered auth infrastructure placeholders")


def _register_blueprints(app: Flask) -> None:
    app.register_blueprint(health_bp)
    logger.debug("Registered health check blueprint")

    # TODO: Register auth blueprints as implemented
    # app.register_blueprint(auth_bp)      # /api/v1/auth/login, /logout, /refresh
    # app.register_blueprint(token_bp)     # /api/v1/auth/token/verify, /revoke
    # app.register_blueprint(user_bp)      # /api/v1/users/me, /change-password


def _setup_swagger(app: Flask, config: Config) -> None:
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
            "title": "Auth Service",
            "description": "Authentication and authorization service",
            "version": "1.0.0",
        },
    }

    Swagger(app, config=swagger_config, template=swagger_template)
    logger.debug("Swagger/OpenAPI documentation configured")
