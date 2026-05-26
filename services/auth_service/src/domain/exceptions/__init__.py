"""Auth domain exceptions package."""
from .auth_errors import (
    AuthDomainError, InvalidTokenError, ExpiredTokenError, RevokedTokenError,
    TokenFamilyCompromisedError, OAuthProviderError, OAuthStateMismatchError,
    OAuthCodeExpiredError, UserNotFoundError, UserInactiveError, InsufficientRolesError,
)
__all__ = [
    "AuthDomainError", "InvalidTokenError", "ExpiredTokenError", "RevokedTokenError",
    "TokenFamilyCompromisedError", "OAuthProviderError", "OAuthStateMismatchError",
    "OAuthCodeExpiredError", "UserNotFoundError", "UserInactiveError", "InsufficientRolesError",
]
