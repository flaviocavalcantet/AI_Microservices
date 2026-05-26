# Flask application factory

from flask import Flask
from flask_cors import CORS
from flasgger import Swagger

from ..config import Config, get_config
from ..container import ServiceContainer, init_container
from ..context import RequestContextManager
from ..errors import register_error_handlers
from ..application.use_cases.oauth_login import OAuthLoginUseCase
from ..application.use_cases.refresh_token import RefreshTokenUseCase
from ..application.use_cases.token_ops import RevokeTokenUseCase, ValidateTokenUseCase
from ..infrastructure.events.noop_publisher import NoOpEventPublisher
from ..infrastructure.oauth.github_provider import GitHubOAuthProvider
from ..infrastructure.repositories.in_memory_refresh_token_repository import (
    InMemoryRefreshTokenRepository,
)
from ..infrastructure.repositories.in_memory_user_repository import InMemoryUserRepository
from ..infrastructure.security.authorization import RoleBasedAuthorizationPolicy
from ..infrastructure.security.jwt_service import JwtTokenService
from ..infrastructure.security.oauth_registry import OAuthProviderRegistry
from ..infrastructure.security.oauth_state_store import InMemoryOAuthStateStore
from ..logger import setup_logging, get_logger
from .routes.health import health_bp
from .routes.v1.auth import auth_bp

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
    _register_use_cases(container, config)

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

    _register_blueprints(app)

    if config.SWAGGER_ENABLED:
        _setup_swagger(app, config)

    logger.info(
        "Flask application created successfully",
        extra={"service": config.SERVICE_NAME},
    )

    return app


def _register_auth_infrastructure(container: ServiceContainer, config: Config) -> None:
    """Register auth infrastructure adapters."""

    allow_dev = config.FLASK_ENV in ("development", "testing", "dev", "test")

    container.register(
        "token_service",
        lambda: JwtTokenService.from_settings(
            secret_key=config.JWT_SECRET_KEY,
            algorithm=config.JWT_ALGORITHM,
            issuer=config.JWT_ISSUER,
            audience=config.JWT_AUDIENCE,
            access_token_ttl_seconds=config.JWT_ACCESS_TOKEN_SECONDS,
            refresh_token_ttl_seconds=config.refresh_token_ttl_seconds(),
            allow_dev_secret=allow_dev,
        ),
        singleton=True,
    )
    container.register("user_repository", InMemoryUserRepository, singleton=True)
    container.register(
        "refresh_token_repository", InMemoryRefreshTokenRepository, singleton=True
    )
    container.register("event_publisher", NoOpEventPublisher, singleton=True)
    container.register(
        "oauth_state_store",
        lambda: InMemoryOAuthStateStore(ttl_minutes=config.OAUTH_STATE_TTL_MINUTES),
        singleton=True,
    )
    container.register("authorization_policy", RoleBasedAuthorizationPolicy, singleton=True)

    def _build_oauth_registry() -> OAuthProviderRegistry:
        registry = OAuthProviderRegistry()
        if config.GITHUB_CLIENT_ID and config.GITHUB_CLIENT_SECRET:
            registry.register(
                "github",
                GitHubOAuthProvider(
                    client_id=config.GITHUB_CLIENT_ID,
                    client_secret=config.GITHUB_CLIENT_SECRET,
                    redirect_uri=config.GITHUB_REDIRECT_URI,
                    scopes=config.GITHUB_OAUTH_SCOPES,
                ),
            )
            logger.info("Registered GitHub OAuth provider")
        else:
            logger.warning(
                "GitHub OAuth not configured — set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET"
            )
        return registry

    container.register("oauth_provider_registry", _build_oauth_registry, singleton=True)
    logger.debug("Registered auth infrastructure")


def _register_use_cases(container: ServiceContainer, config: Config) -> None:
    """Wire application use cases with port implementations."""

    def _oauth_login() -> OAuthLoginUseCase:
        return OAuthLoginUseCase(
            token_service=container.resolve("token_service"),
            user_repository=container.resolve("user_repository"),
            refresh_token_repository=container.resolve("refresh_token_repository"),
            event_publisher=container.resolve("event_publisher"),
            refresh_token_ttl_days=config.REFRESH_TOKEN_EXPIRATION_DAYS,
        )

    def _refresh_token() -> RefreshTokenUseCase:
        return RefreshTokenUseCase(
            token_service=container.resolve("token_service"),
            user_repository=container.resolve("user_repository"),
            refresh_token_repository=container.resolve("refresh_token_repository"),
            event_publisher=container.resolve("event_publisher"),
            refresh_token_ttl_days=config.REFRESH_TOKEN_EXPIRATION_DAYS,
            expires_in_seconds=config.JWT_ACCESS_TOKEN_SECONDS,
        )

    def _validate_token() -> ValidateTokenUseCase:
        return ValidateTokenUseCase(token_service=container.resolve("token_service"))

    def _revoke_token() -> RevokeTokenUseCase:
        return RevokeTokenUseCase(
            refresh_token_repository=container.resolve("refresh_token_repository"),
            event_publisher=container.resolve("event_publisher"),
        )

    container.register("oauth_login_use_case", _oauth_login, singleton=True)
    container.register("refresh_token_use_case", _refresh_token, singleton=True)
    container.register("validate_token_use_case", _validate_token, singleton=True)
    container.register("revoke_token_use_case", _revoke_token, singleton=True)


def _register_blueprints(app: Flask) -> None:
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    logger.debug("Registered health and auth blueprints")


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
        "tags": [
            {
                "name": "Authentication",
                "description": "OAuth login, token refresh, and session management",
            },
        ],
    }

    Swagger(app, config=swagger_config, template=swagger_template)
    logger.debug("Swagger/OpenAPI documentation configured")
