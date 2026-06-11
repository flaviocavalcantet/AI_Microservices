"""In-memory user repository (no database persistence)."""

from __future__ import annotations

import threading
from typing import Dict, List, Optional, Tuple

from ...application.ports.interfaces import IUserRepository
from ...domain.entities.user import User
from ...domain.exceptions.auth_errors import UserNotFoundError


class InMemoryUserRepository(IUserRepository):
    """Thread-safe in-memory user store keyed by id and (provider, provider_user_id)."""

    def __init__(self) -> None:
        self._by_id: Dict[str, User] = {}
        self._by_provider: Dict[Tuple[str, str], str] = {}
        self._by_username: Dict[str, str] = {}  # username → user_id
        self._lock = threading.Lock()

    def find_by_id(self, user_id: str) -> Optional[User]:
        with self._lock:
            return self._by_id.get(user_id)

    def find_by_provider(self, provider: str, provider_user_id: str) -> Optional[User]:
        with self._lock:
            user_id = self._by_provider.get((provider, provider_user_id))
            return self._by_id.get(user_id) if user_id else None

    def find_by_email(self, email: str) -> Optional[User]:
        with self._lock:
            for user in self._by_id.values():
                if user.email.lower() == email.lower():
                    return user
        return None

    def find_by_username(self, username: str) -> Optional[User]:
        with self._lock:
            user_id = self._by_username.get(username.lower())
            return self._by_id.get(user_id) if user_id else None

    def save(self, user: User) -> User:
        with self._lock:
            self._by_id[user.id] = user
            self._by_provider[(user.provider, user.provider_user_id)] = user.id
            if user.username:
                self._by_username[user.username.lower()] = user.id
        return user

    def list_all(self) -> List[User]:
        with self._lock:
            return list(self._by_id.values())

    def update_roles(self, user_id: str, roles: List[str]) -> User:
        with self._lock:
            user = self._by_id.get(user_id)
            if user is None:
                raise UserNotFoundError(user_id)
            user.roles = list(roles)
            return user
