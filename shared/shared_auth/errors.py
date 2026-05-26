"""Authorization-specific error classes.

Extends the domain error model with authorization-specific exceptions.
"""

from typing import Optional, Dict, Any


class AuthorizationError(Exception):
    """Base authorization error.
    
    Raised when authorization checks fail (authentication missing/invalid).
    HTTP 401 Unauthorized.
    """
    
    def __init__(
        self,
        message: str,
        code: str = "UNAUTHORIZED",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        self.status_code = 401
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to API error response."""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


class InsufficientPermissionsError(AuthorizationError):
    """Insufficient permissions for operation.
    
    Raised when user is authenticated but lacks required permissions.
    HTTP 403 Forbidden.
    """
    
    def __init__(
        self,
        message: str,
        required_roles: Optional[list] = None,
        required_permissions: Optional[list] = None,
    ):
        self.required_roles = required_roles or []
        self.required_permissions = required_permissions or []
        
        details = {}
        if self.required_roles:
            details["required_roles"] = self.required_roles
        if self.required_permissions:
            details["required_permissions"] = self.required_permissions
        
        super().__init__(
            message=message,
            code="FORBIDDEN",
            details=details,
        )
        self.status_code = 403


class TokenExpiredError(AuthorizationError):
    """JWT token has expired."""
    
    def __init__(self, message: str = "Token has expired"):
        super().__init__(
            message=message,
            code="TOKEN_EXPIRED",
        )


class InvalidTokenError(AuthorizationError):
    """JWT token is invalid (malformed, unsigned, etc)."""
    
    def __init__(self, message: str = "Invalid token"):
        super().__init__(
            message=message,
            code="INVALID_TOKEN",
        )


class MissingTokenError(AuthorizationError):
    """No authentication token provided."""
    
    def __init__(self, message: str = "Authentication token required"):
        super().__init__(
            message=message,
            code="MISSING_TOKEN",
        )


class InvalidClaimsError(AuthorizationError):
    """JWT claims are invalid (missing required claims, etc)."""
    
    def __init__(
        self,
        message: str = "Invalid token claims",
        missing_claims: Optional[list] = None,
    ):
        details = {}
        if missing_claims:
            details["missing_claims"] = missing_claims
        
        super().__init__(
            message=message,
            code="INVALID_CLAIMS",
            details=details,
        )


class ResourceOwnershipError(AuthorizationError):
    """User is not the owner of resource and cannot perform action."""
    
    def __init__(
        self,
        message: str = "Not authorized to access this resource",
        resource_id: Optional[str] = None,
    ):
        details = {}
        if resource_id:
            details["resource_id"] = resource_id
        
        super().__init__(
            message=message,
            code="FORBIDDEN",
            details=details,
        )
        self.status_code = 403


class PolicyEvaluationError(Exception):
    """Error during authorization policy evaluation."""
    
    def __init__(self, message: str, policy_name: Optional[str] = None):
        self.message = message
        self.policy_name = policy_name
        super().__init__(self.message)
