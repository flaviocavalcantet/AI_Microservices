"""Consume event use case."""

from ...domain.entities.notification import Notification
from ...domain.value_objects.event import EventEnvelope
from ..ports.event_consumer import EventConsumer
from ..ports.notification_channel import NotificationChannel


class ConsumeEventUseCase(EventConsumer):
    """Convert consumed events into logged notification intents."""

    def __init__(self, channel: NotificationChannel):
        self.channel = channel

    def consume(self, event: EventEnvelope) -> dict:
        notification = Notification(
            channel=self.channel.name,
            event_type=event.event_type,
            payload=event.payload,
        )
        return self.channel.send(notification)
