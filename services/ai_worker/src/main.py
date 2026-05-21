# Application entry point

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from .config import get_config
from .logger import get_logger
from .presentation.app import create_app

logger = get_logger(__name__)


def main():
    try:
        config = get_config()
        app = create_app(config=config)

        logger.info(
            "Starting ai_worker HTTP probe server",
            extra={
                "host": config.SERVICE_HOST,
                "port": config.SERVICE_PORT,
                "queue": config.CELERY_TASK_DEFAULT_QUEUE,
            },
        )

        app.run(
            host=config.SERVICE_HOST,
            port=config.SERVICE_PORT,
            debug=config.DEBUG,
            use_reloader=config.DEBUG,
        )

    except Exception as e:
        logger.error(f"Failed to start ai_worker: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
