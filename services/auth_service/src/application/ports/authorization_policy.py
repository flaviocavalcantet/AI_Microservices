"""Authorization policy port for future RBAC support."""

from abc import ABC, abstractmethod
from typing import Sequence


class AuthorizationPolicy(ABC):
    """Interface for role and permission checks."""

    @abstractmethod
    def has_role(self, user_roles: Sequence[str], required_role: str) -> bool:
        raise NotImplementedError
