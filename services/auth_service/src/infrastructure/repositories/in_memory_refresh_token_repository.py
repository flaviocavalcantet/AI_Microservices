"""In-memory refresh token repository (no database persistence)."""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from ...application.ports.interfaces import IRefreshTokenRepository
from ...domain.entities.refresh_token import RefreshToken


class InMemoryRefreshTokenRepository(IRefreshTokenRepository):
    """Thread-safe in-memory refresh token store."""

    def __init__(self) -> None:
        self._by_hash: Dict[str, RefreshToken] = {}
        self._by_session: Dict[str, List[str]] = {}
        self._lock = threading.Lock()

    def save(self, token: RefreshToken) -> RefreshToken:
        with self._lock:
            self._by_hash[token.token_hash] = token
            session_hashes = self._by_session.setdefault(token.session_id, [])
            if token.token_hash not in session_hashes:
                session_hashes.append(token.token_hash)
        return token

    def find_by_hash(self, token_hash: str) -> Optional[RefreshToken]:
        with self._lock:
            return self._by_hash.get(token_hash)

    def find_by_session_id(self, session_id: str) -> List[RefreshToken]:
        with self._lock:
            hashes = self._by_session.get(session_id, [])
            return [self._by_hash[h] for h in hashes if h in self._by_hash]

    def revoke_session(self, session_id: str, reason: str) -> int:
        revoked = 0
        with self._lock:
            hashes = list(self._by_session.get(session_id, []))
            for token_hash in hashes:
                token = self._by_hash.get(token_hash)
                if token and token.revoked_at is None:
                    token.revoke(reason=reason)
                    revoked += 1
        return revoked

    def delete_expired(self) -> int:
        deleted = 0
        with self._lock:
            expired_hashes = [
                h for h, t in self._by_hash.items() if t.is_expired
            ]
            for token_hash in expired_hashes:
                token = self._by_hash.pop(token_hash, None)
                if token:
                    session_list = self._by_session.get(token.session_id, [])
                    if token_hash in session_list:
                        session_list.remove(token_hash)
                    deleted += 1
        return deleted
