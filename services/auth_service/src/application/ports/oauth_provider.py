"""Legacy alias — use IOAuthProvider from interfaces.py."""

from .interfaces import IOAuthProvider as OAuthProvider

__all__ = ["OAuthProvider"]
