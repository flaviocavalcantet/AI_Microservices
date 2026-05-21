"""Token service port for future JWT support."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class TokenService(ABC):
    """Interface for issuing and validating tokens."""

    @abstractmethod
    def issue_access_token(self, subject: str, claims: Dict[str, Any] | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def validate_access_token(self, token: str) -> Dict[str, Any]:
        raise NotImplementedError
