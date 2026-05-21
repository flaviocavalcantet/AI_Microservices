"""Event consumer port."""

from abc import ABC, abstractmethod

from ...domain.value_objects.event import EventEnvelope


class EventConsumer(ABC):
    """Interface for processing consumed events."""

    @abstractmethod
    def consume(self, event: EventEnvelope) -> dict:
        raise NotImplementedError
