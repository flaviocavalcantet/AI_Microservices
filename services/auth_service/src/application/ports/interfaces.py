"""Application layer ports (interfaces).

Defines the contracts that infrastructure adapters must implement.
The application layer depends only on these abstractions — never on concrete implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from ...domain.entities.refresh_token import RefreshToken
from ...domain.entities.user import User
from ...domain.value_objects.token_claims import RefreshTokenClaims, TokenClaims
from ...domain.value_objects.token_payload import IssuedTokenPair


class ITokenService(ABC):
    """Contract for JWT access and refresh token issuance and validation."""

    @abstractmethod
    def issue_access_token(
        self, user: User, session_id: str | None = None
    ) -> Tuple[str, str]:
        """Issue a signed access JWT. Returns (encoded_jwt, jti)."""

    @abstractmethod
    def issue_refresh_token(self, user: User, session_id: str) -> Tuple[str, str]:
        """Issue a signed refresh JWT. Returns (encoded_jwt, jti)."""

    @abstractmethod
    def issue_token_pair(self, user: User, session_id: str) -> IssuedTokenPair:
        """Issue access + refresh JWT pair with configured TTLs."""

    @abstractmethod
    def validate_access_token(self, token: str) -> TokenClaims:
        """Validate access JWT signature and claims."""

    @abstractmethod
    def validate_refresh_token(self, token: str) -> RefreshTokenClaims:
        """Validate refresh JWT signature and claims."""

    @abstractmethod
    def decode_unverified(self, token: str) -> Dict[str, Any]:
        """Decode without verifying signature — for inspecting expired tokens."""


class IOAuthProvider(ABC):
    """Contract for an external OAuth provider integration."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Canonical provider name, e.g. 'github', 'google'."""

    @abstractmethod
    def build_authorization_url(self, state: str, code_challenge: str) -> str:
        """Build the redirect URL for the OAuth consent screen."""

    @abstractmethod
    def exchange_code(self, code: str, state: str, code_verifier: str) -> Dict[str, Any]:
        """Exchange authorization code for provider tokens + userinfo."""

    @abstractmethod
    def get_userinfo(self, access_token: str) -> Dict[str, Any]:
        """Fetch user profile using a provider access token."""


class IUserRepository(ABC):
    """Contract for user persistence."""

    @abstractmethod
    def find_by_id(self, user_id: str) -> Optional[User]: ...

    @abstractmethod
    def find_by_provider(self, provider: str, provider_user_id: str) -> Optional[User]: ...

    @abstractmethod
    def find_by_email(self, email: str) -> Optional[User]: ...

    @abstractmethod
    def find_by_username(self, username: str) -> Optional[User]:
        """Look up a local-auth user by username."""

    @abstractmethod
    def save(self, user: User) -> User: ...

    @abstractmethod
    def list_all(self) -> List[User]:
        """Return all users (admin use only)."""

    @abstractmethod
    def update_roles(self, user_id: str, roles: List[str]) -> User:
        """Replace the roles list for *user_id* and return the updated user."""


class IRefreshTokenRepository(ABC):
    """Contract for refresh token persistence."""

    @abstractmethod
    def save(self, token: RefreshToken) -> RefreshToken: ...

    @abstractmethod
    def find_by_hash(self, token_hash: str) -> Optional[RefreshToken]: ...

    @abstractmethod
    def find_by_session_id(self, session_id: str) -> List[RefreshToken]: ...

    @abstractmethod
    def revoke_session(self, session_id: str, reason: str) -> int:
        """Revoke all tokens in a session family. Returns revoked count."""

    @abstractmethod
    def delete_expired(self) -> int:
        """Housekeeping — returns deleted count."""


class IAuthorizationPolicy(ABC):
    """Contract for role and permission checks."""

    @abstractmethod
    def has_role(self, user_roles: List[str], required_role: str) -> bool: ...

    @abstractmethod
    def has_any_role(self, user_roles: List[str], required_roles: List[str]) -> bool: ...


class IEventPublisher(ABC):
    """Contract for publishing domain events to the message bus."""

    @abstractmethod
    def publish(self, event: Any) -> None: ...
