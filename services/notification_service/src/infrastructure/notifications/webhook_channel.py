"""Webhook notification channel placeholder."""

from ...application.ports.notification_channel import NotificationChannel
from ...domain.entities.notification import Notification


class WebhookNotificationChannel(NotificationChannel):
    """Future webhook adapter skeleton."""

    @property
    def name(self) -> str:
        return "webhook"

    def send(self, notification: Notification) -> dict:
        raise NotImplementedError("Webhook notifications are not implemented yet")
