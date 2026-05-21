"""JWT adapter placeholder.

No token issuing or validation is implemented yet.
"""

from typing import Any, Dict

from ...application.ports.token_service import TokenService


class JwtTokenService(TokenService):
    """JWT-ready adapter skeleton."""

    def __init__(self, secret_key: str, algorithm: str, issuer: str, audience: str):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.issuer = issuer
        self.audience = audience

    def issue_access_token(self, subject: str, claims: Dict[str, Any] | None = None) -> str:
        raise NotImplementedError("JWT issuing is not implemented yet")

    def validate_access_token(self, token: str) -> Dict[str, Any]:
        raise NotImplementedError("JWT validation is not implemented yet")
