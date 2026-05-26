"""No-op event publisher until RabbitMQ adapter is wired."""

from __future__ import annotations

import logging
from typing import Any

from ...application.ports.interfaces import IEventPublisher

logger = logging.getLogger(__name__)


class NoOpEventPublisher(IEventPublisher):
    """Logs domain events without publishing to a message bus."""

    def publish(self, event: Any) -> None:
        logger.debug(
            "Domain event (no-op publisher)",
            extra={"event_type": getattr(event, "event_type", type(event).__name__)},
        )
