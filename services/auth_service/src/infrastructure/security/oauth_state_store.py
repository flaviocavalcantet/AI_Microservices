"""In-memory OAuth state store (development / no-DB mode)."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional


@dataclass
class OAuthStateEntry:
    state: str
    code_challenge: str
    code_verifier: str
    provider: str
    redirect_uri: Optional[str]
    expires_at: datetime


class InMemoryOAuthStateStore:
    """Stores OAuth state + PKCE challenge until callback."""

    def __init__(self, ttl_minutes: int = 10):
        self._ttl = timedelta(minutes=ttl_minutes)
        self._entries: Dict[str, OAuthStateEntry] = {}
        self._lock = threading.Lock()

    def save(
        self,
        state: str,
        code_challenge: str,
        code_verifier: str,
        provider: str,
        redirect_uri: Optional[str] = None,
    ) -> None:
        with self._lock:
            self._entries[state] = OAuthStateEntry(
                state=state,
                code_challenge=code_challenge,
                code_verifier=code_verifier,
                provider=provider,
                redirect_uri=redirect_uri,
                expires_at=datetime.now(timezone.utc) + self._ttl,
            )

    def consume(self, state: str) -> Optional[OAuthStateEntry]:
        """Return and remove state entry (one-time use)."""
        with self._lock:
            entry = self._entries.pop(state, None)
        if entry is None:
            return None
        if entry.expires_at <= datetime.now(timezone.utc):
            return None
        return entry
