"""OAuth provider port for future OAuth flows."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class OAuthProvider(ABC):
    """Interface for external OAuth provider integrations."""

    @abstractmethod
    def get_authorization_url(self, state: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def exchange_code(self, code: str) -> Dict[str, Any]:
        raise NotImplementedError
