"""Shared authentication and authorization module.

Provides:
- Role-based access control (RBAC)
- JWT validation and claims extraction
- Authorization decorators and middleware
- Reusable authorization policies
- Future extensibility for permissions
"""

__version__ = "1.0.0"
__author__ = "AI Platform Team"

from .models import Role, AuthContext, Permission
from .policies import AuthorizationPolicy, RoleBasedAuthorizationPolicy
from .middleware import (
    require_authenticated,
    require_role,
    require_permission,
    require_any_role,
)
from .errors import AuthorizationError, InsufficientPermissionsError
from .jwt_handler import JWTHandler

__all__ = [
    "Role",
    "AuthContext",
    "Permission",
    "AuthorizationPolicy",
    "RoleBasedAuthorizationPolicy",
    "require_authenticated",
    "require_role",
    "require_permission",
    "require_any_role",
    "AuthorizationError",
    "InsufficientPermissionsError",
    "JWTHandler",
]
