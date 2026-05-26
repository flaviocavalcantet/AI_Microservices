"""PKCE helpers for OAuth2 authorization code flow."""

from __future__ import annotations

import base64
import hashlib
import secrets


def generate_code_verifier(length: int = 64) -> str:
    """Generate a cryptographically random PKCE code verifier."""
    return secrets.token_urlsafe(length)[:128]


def generate_code_challenge(code_verifier: str) -> str:
    """S256 code challenge from verifier."""
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def generate_oauth_state() -> str:
    """CSRF state nonce for OAuth redirect."""
    return secrets.token_urlsafe(32)
