# Application entry point
import sys
import logging


# Add shared imports for shared utilities
from shared.shared_config import load_env, get_settings
from src.presentation.app import create_app
from src.logger import get_logger

# Load environment variables from .env files FIRST
load_env(verbose=True)

# Setup basic logging for startup
logging.basicConfig(level=logging.INFO)
logger = get_logger(__name__)


def validate_startup():
    """Validate configuration at startup

    Raises:
        ValueError: If critical configuration is missing or invalid
    """
    try:
        settings = get_settings()

        logger.info(
            "Configuration validated",
            extra={
                "environment": settings.FLASK_ENV,
                "log_level": settings.LOG_LEVEL,
                "log_format": settings.LOG_FORMAT,
            },
        )

        return settings

    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        raise


def main():
    """Main entry point for the Flask application

    1. Loads environment configuration
    2. Validates startup conditions
    3. Creates Flask application
    4. Starts development/production server
    """

    try:
        # Validate configuration
        settings = validate_startup()

        # Create Flask application with configuration
        app = create_app()

        # Get configuration
        config = app.config

        # Log startup information
        logger.info(
            f"Starting {config.get('SERVICE_NAME', 'Auth Service')}",
            extra={
                "environment": config.get("FLASK_ENV", "development"),
                "debug": config.get("DEBUG", False),
                "host": config.get("SERVICE_HOST", "0.0.0.0"),
                "port": config.get("SERVICE_PORT", 5001),
            },
        )
       
       # Run development server
        app.run(
            host="0.0.0.0",
            port=5000,
            debug= False,
            use_reloader=False,
        )

    except Exception as e:
        logger.error(f"Failed to start application: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()