"""Logging notification channel."""

from ...application.ports.notification_channel import NotificationChannel
from ...domain.entities.notification import Notification
from ...logger import get_logger

logger = get_logger(__name__)


class LogNotificationChannel(NotificationChannel):
    """Notification channel that logs intent only."""

    @property
    def name(self) -> str:
        return "log"

    def send(self, notification: Notification) -> dict:
        logger.info(
            "Notification intent logged",
            extra={
                "notification_id": notification.id,
                "event_type": notification.event_type,
                "channel": self.name,
            },
        )
        return {
            "status": "logged",
            "notification_id": notification.id,
            "channel": self.name,
            "event_type": notification.event_type,
        }
