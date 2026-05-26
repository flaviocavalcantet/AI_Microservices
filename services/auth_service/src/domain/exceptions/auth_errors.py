"""Auth domain exceptions.

Pure Python — no framework dependency.
These propagate up through use cases and are caught at the presentation layer.
"""


class AuthDomainError(Exception):
    """Base for all auth domain errors."""


class InvalidTokenError(AuthDomainError):
    """Token signature is invalid or payload is malformed."""


class ExpiredTokenError(AuthDomainError):
    """Token has passed its expiry time."""


class RevokedTokenError(AuthDomainError):
    """Token has been explicitly revoked."""


class TokenFamilyCompromisedError(AuthDomainError):
    """A revoked token in a family was reused — possible theft detected.

    When raised, the entire token family (session) must be invalidated.
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(
            f"Revoked refresh token reused in session {session_id!r}. "
            "Entire session invalidated."
        )


class OAuthProviderError(AuthDomainError):
    """OAuth provider returned an error or unexpected response."""


class OAuthStateMismatchError(AuthDomainError):
    """CSRF state parameter does not match the stored state."""


class OAuthCodeExpiredError(AuthDomainError):
    """Authorization code has expired or already been used."""


class UserNotFoundError(AuthDomainError):
    def __init__(self, identifier: str) -> None:
        super().__init__(f"User not found: {identifier!r}")


class UserInactiveError(AuthDomainError):
    def __init__(self, user_id: str) -> None:
        super().__init__(f"User account is inactive: {user_id!r}")


class InsufficientRolesError(AuthDomainError):
    def __init__(self, required: str, held: list) -> None:
        super().__init__(
            f"Required role {required!r} not in user roles {held!r}"
        )
