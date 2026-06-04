"""JWT token validation and claims extraction.

Validates JWT tokens and extracts auth context for request processing.
Supports both HS256 (symmetric) and RS256 (asymmetric) algorithms.

Design:
- Single responsibility: Validate and extract claims
- No side effects: Pure function that returns AuthContext
- Testable: Can be tested independently
- Extensible: Can be subclassed for custom claim handling
"""

import jwt
from datetime import datetime
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

from .models import Role, AuthContext, ServicePrincipal
from .errors import (
    InvalidTokenError,
    TokenExpiredError,
    MissingTokenError,
    InvalidClaimsError,
)


class JWTHandler(ABC):
    """Abstract JWT handler for token validation.
    
    Subclass for specific signing strategies (HS256, RS256).
    """
    
    REQUIRED_CLAIMS = {"iss", "aud", "sub", "iat", "exp", "roles", "session_id", "jti"}
    OPTIONAL_CLAIMS = {"email", "provider", "display_name", "avatar_url"}
    
    @abstractmethod
    def validate_signature(self, token: str) -> Dict[str, Any]:
        """Validate token signature and return claims.
        
        Raises:
            InvalidTokenError: If signature is invalid
            TokenExpiredError: If token is expired
        """
        raise NotImplementedError
    
    def validate_token(self, token: str) -> AuthContext:
        """Validate token and extract auth context.
        
        Args:
            token: JWT token string (without 'Bearer ' prefix)
            
        Returns:
            AuthContext with user info and roles
            
        Raises:
            MissingTokenError: If token is None/empty
            InvalidTokenError: If token format is invalid
            TokenExpiredError: If token is expired
            InvalidClaimsError: If required claims are missing
        """
        if not token or not token.strip():
            raise MissingTokenError()
        
        # Validate signature and get claims
        try:
            claims = self.validate_signature(token)
        except jwt.ExpiredSignatureError:
            raise TokenExpiredError()
        except jwt.InvalidSignatureError:
            raise InvalidTokenError("Invalid token signature")
        except jwt.DecodeError:
            raise InvalidTokenError("Token decode failed")
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError(str(e))
        
        # Validate required claims
        missing_claims = self.REQUIRED_CLAIMS - set(claims.keys())
        if missing_claims:
            raise InvalidClaimsError(missing_claims=list(missing_claims))
        
        # Parse roles
        try:
            role_strings = claims.get("roles", [])
            if isinstance(role_strings, str):
                role_strings = [role_strings]
            
            roles = Role.from_list(role_strings)
            
            if not roles:
                raise InvalidClaimsError(
                    message="No valid roles in token claims",
                    missing_claims=["roles"]
                )
        except (ValueError, TypeError) as e:
            raise InvalidClaimsError(message=f"Invalid roles claim: {str(e)}")
        
        # Create AuthContext
        try:
            auth_context = AuthContext(
                user_id=claims["sub"],
                roles=roles,
                session_id=claims["session_id"],
                issued_at=datetime.utcfromtimestamp(claims["iat"]),
                expires_at=datetime.utcfromtimestamp(claims["exp"]),
                jti=claims["jti"],
                email=claims.get("email"),
                provider=claims.get("provider"),
                extra_claims={
                    k: v for k, v in claims.items()
                    if k not in self.REQUIRED_CLAIMS and k not in self.OPTIONAL_CLAIMS
                },
            )
        except (KeyError, ValueError, TypeError) as e:
            raise InvalidClaimsError(message=f"Failed to construct auth context: {str(e)}")
        
        return auth_context
    
    def extract_bearer_token(self, auth_header: Optional[str]) -> str:
        """Extract token from Authorization header.
        
        Args:
            auth_header: Authorization header value (e.g., "Bearer <token>")
            
        Returns:
            Token string
            
        Raises:
            MissingTokenError: If header is missing or malformed
        """
        if not auth_header:
            raise MissingTokenError()
        
        parts = auth_header.split()
        
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise InvalidTokenError("Authorization header must be 'Bearer <token>'")
        
        return parts[1]


class HMACJWTHandler(JWTHandler):
    """JWT handler using HMAC (HS256) - Symmetric signing.
    
    Best for:
    - Development environments
    - Single service issuance
    - Shared secret deployment
    
    NOT recommended for production with multiple independent services.
    """
    
    def __init__(
        self,
        secret_key: str,
        issuer: str,
        audience: str,
        algorithms: Optional[list] = None,
    ):
        """Initialize HMAC JWT handler.
        
        Args:
            secret_key: Shared secret key (min 32 chars in production)
            issuer: Expected 'iss' claim value
            audience: Expected 'aud' claim value
            algorithms: Allowed algorithms (default: ["HS256"])
        """
        self.secret_key = secret_key
        self.issuer = issuer
        self.audience = audience
        self.algorithms = algorithms or ["HS256"]
    
    def validate_signature(self, token: str) -> Dict[str, Any]:
        """Validate HMAC signature."""
        claims = jwt.decode(
            token,
            self.secret_key,
            algorithms=self.algorithms,
            issuer=self.issuer,
            audience=self.audience,
        )
        
        # Validate issuer and audience
        if claims.get("iss") != self.issuer:
            raise InvalidTokenError(f"Invalid issuer: expected '{self.issuer}'")
        
        if claims.get("aud") != self.audience:
            raise InvalidTokenError(f"Invalid audience: expected '{self.audience}'")
        
        return claims


class RSAJWTHandler(JWTHandler):
    """JWT handler using RSA (RS256) - Asymmetric signing.
    
    Best for:
    - Production environments
    - Multiple independent services
    - External token validation via public key
    - OAuth2 servers
    
    The auth-service holds the private key; other services verify with public key.
    """
    
    def __init__(
        self,
        public_key: str,
        issuer: str,
        audience: str,
        algorithms: Optional[list] = None,
    ):
        """Initialize RSA JWT handler.
        
        Args:
            public_key: RSA public key (PEM format)
            issuer: Expected 'iss' claim value
            audience: Expected 'aud' claim value
            algorithms: Allowed algorithms (default: ["RS256"])
        """
        self.public_key = public_key
        self.issuer = issuer
        self.audience = audience
        self.algorithms = algorithms or ["RS256"]
    
    def validate_signature(self, token: str) -> Dict[str, Any]:
        """Validate RSA signature."""
        claims = jwt.decode(
            token,
            self.public_key,
            algorithms=self.algorithms,
            issuer=self.issuer,
            audience=self.audience,
        )
        
        # Validate issuer and audience
        if claims.get("iss") != self.issuer:
            raise InvalidTokenError(f"Invalid issuer: expected '{self.issuer}'")
        
        if claims.get("aud") != self.audience:
            raise InvalidTokenError(f"Invalid audience: expected '{self.audience}'")
        
        return claims


def create_jwt_handler(
    algorithm: str,
    secret_or_key: str,
    issuer: str,
    audience: str,
) -> JWTHandler:
    """Factory function to create appropriate JWT handler.
    
    Args:
        algorithm: "HS256" or "RS256"
        secret_or_key: Shared secret (HS256) or public key (RS256)
        issuer: Expected 'iss' claim value
        audience: Expected 'aud' claim value
        
    Returns:
        Configured JWTHandler
        
    Raises:
        ValueError: If algorithm is not supported
    """
    if algorithm == "HS256":
        return HMACJWTHandler(secret_or_key, issuer, audience)
    elif algorithm == "RS256":
        return RSAJWTHandler(secret_or_key, issuer, audience)
    else:
        raise ValueError(f"Unsupported JWT algorithm: {algorithm}")
