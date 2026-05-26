"""Legacy alias — use IAuthorizationPolicy from interfaces.py."""

from .interfaces import IAuthorizationPolicy as AuthorizationPolicy

__all__ = ["AuthorizationPolicy"]
