"""Event consumption tasks.

Tasks log notification intent only; no real notifications are sent.
"""

from ...application.use_cases.consume_event import ConsumeEventUseCase
from ...domain.value_objects.event import EventEnvelope
from ...infrastructure.messaging.celery_app import celery
from ...infrastructure.notifications.log_channel import LogNotificationChannel


@celery.task(name="notification_service.events.consume")
def consume_event(event_data: dict) -> dict:
    """Consume an event and log the notification intent."""

    event = EventEnvelope.from_dict(event_data)
    consumer = ConsumeEventUseCase(channel=LogNotificationChannel())
    return consumer.consume(event)
