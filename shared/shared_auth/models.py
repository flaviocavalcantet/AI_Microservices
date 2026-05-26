"""Authorization models and domain objects.

Defines core authorization concepts:
- Role enum with admin, user, worker
- Permission model for future extensibility
- AuthContext for storing authenticated request info
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Any, Dict
from datetime import datetime


class Role(str, Enum):
    """Available roles in the system.
    
    Roles are hierarchical:
    - admin: Full system access, manages other users
    - user: Standard authenticated user, can perform basic operations
    - worker: Service-to-service operations, limited scope
    
    Future: Can be extended with custom roles at runtime.
    """
    ADMIN = "admin"
    USER = "user"
    WORKER = "worker"
    
    @classmethod
    def is_valid(cls, role: str) -> bool:
        """Check if role string is valid."""
        return role in [r.value for r in cls]
    
    @classmethod
    def from_list(cls, roles: List[str]) -> List["Role"]:
        """Convert role strings to Role enum values.
        
        Args:
            roles: List of role strings
            
        Returns:
            List of Role enums, filtering invalid roles
        """
        valid_roles = []
        for role in roles:
            if cls.is_valid(role):
                valid_roles.append(cls(role))
        return valid_roles


@dataclass
class Permission:
    """Permission model for fine-grained authorization.
    
    Supports RBAC (role-based) and ABAC (attribute-based) controls.
    
    Example:
        Permission(resource="job", action="create", owner_required=False)
        Permission(resource="job", action="delete", owner_required=True)
    """
    resource: str
    action: str
    owner_required: bool = False
    
    def __eq__(self, other):
        if not isinstance(other, Permission):
            return False
        return (self.resource == other.resource and 
                self.action == other.action and
                self.owner_required == other.owner_required)
    
    def __hash__(self):
        return hash((self.resource, self.action, self.owner_required))
    
    @property
    def identifier(self) -> str:
        """Get unique permission identifier."""
        return f"{self.resource}:{self.action}"


@dataclass
class AuthContext:
    """Authenticated request context extracted from JWT.
    
    Injected into Flask request context (g.auth_context) by middleware.
    Available to route handlers and use cases.
    
    Attributes:
        user_id: Unique user/service identifier (from JWT 'sub' claim)
        roles: List of assigned roles
        email: User email (optional)
        session_id: Session identifier for token family tracking
        provider: OAuth provider name (optional)
        issued_at: Token issuance time
        expires_at: Token expiration time
        jti: Unique token ID for revocation tracking
        
    Example:
        auth_ctx = g.auth_context
        if Role.ADMIN in auth_ctx.roles:
            # Perform admin action
    """
    user_id: str
    roles: List[Role]
    session_id: str
    issued_at: datetime
    expires_at: datetime
    jti: str
    email: Optional[str] = None
    provider: Optional[str] = None
    extra_claims: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize extra_claims if not provided."""
        if self.extra_claims is None:
            self.extra_claims = {}
    
    def has_role(self, role: Role) -> bool:
        """Check if user has specific role."""
        return role in self.roles
    
    def has_any_role(self, roles: List[Role]) -> bool:
        """Check if user has any of the specified roles."""
        return any(role in self.roles for role in roles)
    
    def has_all_roles(self, roles: List[Role]) -> bool:
        """Check if user has all specified roles."""
        return all(role in self.roles for role in roles)
    
    def is_admin(self) -> bool:
        """Convenience check for admin role."""
        return self.has_role(Role.ADMIN)
    
    def is_worker(self) -> bool:
        """Convenience check for worker role."""
        return self.has_role(Role.WORKER)
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        return datetime.utcnow() > self.expires_at
    
    def __repr__(self) -> str:
        return f"AuthContext(user_id={self.user_id}, roles={self.roles})"


@dataclass
class ServicePrincipal:
    """Service-to-service authentication context.
    
    Used when a service calls another service with JWT.
    
    Example:
        principal = ServicePrincipal(
            service_id="api-service",
            service_name="api_service",
            roles=[Role.WORKER]
        )
    """
    service_id: str
    service_name: str
    roles: List[Role]
    issued_at: datetime
    expires_at: datetime
    jti: str
    
    def is_service(self) -> bool:
        """Check if principal is a service (not a user)."""
        return Role.WORKER in self.roles
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        return datetime.utcnow() > self.expires_at
