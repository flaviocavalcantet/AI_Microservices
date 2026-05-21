"""Email notification channel placeholder."""

from ...application.ports.notification_channel import NotificationChannel
from ...domain.entities.notification import Notification


class EmailNotificationChannel(NotificationChannel):
    """Future email adapter skeleton."""

    @property
    def name(self) -> str:
        return "email"

    def send(self, notification: Notification) -> dict:
        raise NotImplementedError("Email notifications are not implemented yet")
