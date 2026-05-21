"""Notification channel port."""

from abc import ABC, abstractmethod

from ...domain.entities.notification import Notification


class NotificationChannel(ABC):
    """Interface for future notification delivery channels."""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def send(self, notification: Notification) -> dict:
        raise NotImplementedError
