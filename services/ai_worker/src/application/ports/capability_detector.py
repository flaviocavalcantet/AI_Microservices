"""Capability detection port."""

from abc import ABC, abstractmethod

from ...domain.value_objects.worker_capabilities import WorkerCapabilities


class CapabilityDetector(ABC):
    """Interface for detecting worker runtime capabilities."""

    @abstractmethod
    def detect(self) -> WorkerCapabilities:
        raise NotImplementedError
