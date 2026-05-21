"""Future AI workload runner port."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class WorkloadRunner(ABC):
    """Interface for future AI/data science workload execution."""

    @abstractmethod
    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError
