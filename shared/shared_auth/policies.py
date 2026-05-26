"""Authorization policies for role-based access control.

Policies encapsulate authorization logic:
- Role-based access (which roles can do X)
- Permission-based access (fine-grained)
- Resource ownership (user owns resource)
- Attribute-based (context-dependent)

Design:
- Policies are testable, pure functions (or classes with evaluation)
- Can be composed for complex authorization rules
- Extensible for custom business logic
- Independent of Flask/HTTP concerns
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from .models import Role, AuthContext, Permission
from .errors import InsufficientPermissionsError, PolicyEvaluationError


class AuthorizationPolicy(ABC):
    """Abstract authorization policy.
    
    Base class for all authorization decision makers.
    Subclass to implement custom authorization logic.
    """
    
    @abstractmethod
    def evaluate(self, auth_context: AuthContext, **kwargs) -> bool:
        """Evaluate authorization decision.
        
        Args:
            auth_context: Authenticated user context
            **kwargs: Additional context (resource_id, action, etc.)
            
        Returns:
            True if authorized, False otherwise
            
        Raises:
            PolicyEvaluationError: If evaluation fails
        """
        raise NotImplementedError
    
    def assert_authorized(self, auth_context: AuthContext, **kwargs) -> None:
        """Assert that authorization is granted, raise if not.
        
        Args:
            auth_context: Authenticated user context
            **kwargs: Additional context
            
        Raises:
            InsufficientPermissionsError: If not authorized
        """
        if not self.evaluate(auth_context, **kwargs):
            raise InsufficientPermissionsError(
                message="Access denied by authorization policy"
            )


class RoleBasedAuthorizationPolicy(AuthorizationPolicy):
    """Role-based authorization policy.
    
    Checks if user has required roles.
    
    Example:
        policy = RoleBasedAuthorizationPolicy()
        policy.require_role(Role.ADMIN)
        policy.assert_authorized(auth_context)
    """
    
    def __init__(self):
        """Initialize policy."""
        self._required_roles: set[Role] = set()
        self._allow_any_role: set[Role] = set()
        self._require_all_roles: set[Role] = set()
    
    def require_role(self, role: Role) -> "RoleBasedAuthorizationPolicy":
        """Require specific role(s).
        
        Alias for require_all_roles for single role.
        """
        self._required_roles.add(role)
        return self
    
    def require_any_role(self, roles: list[Role]) -> "RoleBasedAuthorizationPolicy":
        """Require at least one of the specified roles.
        
        Args:
            roles: List of allowed roles
            
        Returns:
            Self for chaining
        """
        self._allow_any_role.update(roles)
        return self
    
    def require_all_roles(self, roles: list[Role]) -> "RoleBasedAuthorizationPolicy":
        """Require all specified roles.
        
        Args:
            roles: List of required roles
            
        Returns:
            Self for chaining
        """
        self._require_all_roles.update(roles)
        return self
    
    def evaluate(self, auth_context: AuthContext, **kwargs) -> bool:
        """Evaluate role-based authorization.
        
        Returns True if:
        - User has all _required_roles (if any), AND
        - User has all _require_all_roles (if any), AND
        - User has any of _allow_any_role (if any)
        """
        # Check required roles
        if self._required_roles:
            if not auth_context.has_all_roles(list(self._required_roles)):
                return False
        
        # Check require_all_roles
        if self._require_all_roles:
            if not auth_context.has_all_roles(list(self._require_all_roles)):
                return False
        
        # Check allow_any_role
        if self._allow_any_role:
            if not auth_context.has_any_role(list(self._allow_any_role)):
                return False
        
        return True
    
    def copy(self) -> "RoleBasedAuthorizationPolicy":
        """Create a copy of this policy."""
        new_policy = RoleBasedAuthorizationPolicy()
        new_policy._required_roles = self._required_roles.copy()
        new_policy._allow_any_role = self._allow_any_role.copy()
        new_policy._require_all_roles = self._require_all_roles.copy()
        return new_policy


class ResourceOwnershipPolicy(AuthorizationPolicy):
    """Resource ownership authorization policy.
    
    Checks if user is the owner of a resource.
    
    Example:
        policy = ResourceOwnershipPolicy()
        policy.assert_authorized(
            auth_context,
            resource_owner_id="user-123",
        )
    """
    
    def __init__(self, allow_admin_override: bool = True):
        """Initialize resource ownership policy.
        
        Args:
            allow_admin_override: If True, admins can access any resource
        """
        self.allow_admin_override = allow_admin_override
    
    def evaluate(self, auth_context: AuthContext, **kwargs) -> bool:
        """Evaluate resource ownership.
        
        Args:
            auth_context: Authenticated user
            resource_owner_id: The owner of the resource (from kwargs)
            
        Returns:
            True if user owns resource or is admin (if override enabled)
        """
        resource_owner_id = kwargs.get("resource_owner_id")
        
        if resource_owner_id is None:
            raise PolicyEvaluationError("Missing 'resource_owner_id' in policy context")
        
        # Admin override
        if self.allow_admin_override and auth_context.is_admin():
            return True
        
        # Check ownership
        return auth_context.user_id == resource_owner_id


class CompositeAuthorizationPolicy(AuthorizationPolicy):
    """Composite policy combining multiple policies.
    
    Supports AND (all policies must pass) and OR (any policy can pass).
    
    Example:
        # Require admin OR (user AND owner)
        composite = CompositeAuthorizationPolicy(mode="or")
        composite.add(admin_policy)
        composite.add(user_and_owner_policy)
        composite.assert_authorized(auth_context, resource_owner_id="user-123")
    """
    
    def __init__(self, mode: str = "and"):
        """Initialize composite policy.
        
        Args:
            mode: "and" (all policies) or "or" (any policy)
        """
        if mode not in ("and", "or"):
            raise ValueError("mode must be 'and' or 'or'")
        
        self.mode = mode
        self._policies: list[AuthorizationPolicy] = []
    
    def add(self, policy: AuthorizationPolicy) -> "CompositeAuthorizationPolicy":
        """Add policy to composite.
        
        Args:
            policy: Authorization policy to add
            
        Returns:
            Self for chaining
        """
        self._policies.append(policy)
        return self
    
    def evaluate(self, auth_context: AuthContext, **kwargs) -> bool:
        """Evaluate composite policy."""
        if not self._policies:
            return True
        
        if self.mode == "and":
            return all(
                policy.evaluate(auth_context, **kwargs)
                for policy in self._policies
            )
        else:  # or
            return any(
                policy.evaluate(auth_context, **kwargs)
                for policy in self._policies
            )


class PermissionBasedPolicy(AuthorizationPolicy):
    """Permission-based authorization policy.
    
    Checks if user has required permissions.
    Maps roles to permissions.
    
    Example:
        policy = PermissionBasedPolicy()
        policy.grant_permission(Role.ADMIN, Permission("job", "delete"))
        policy.grant_permission(Role.USER, Permission("job", "create"))
        policy.assert_authorized(
            auth_context,
            required_permission=Permission("job", "delete")
        )
    """
    
    def __init__(self):
        """Initialize permission policy."""
        self._role_permissions: Dict[Role, set[Permission]] = {}
    
    def grant_permission(
        self,
        role: Role,
        permission: Permission,
    ) -> "PermissionBasedPolicy":
        """Grant permission to role.
        
        Args:
            role: Role to grant permission to
            permission: Permission to grant
            
        Returns:
            Self for chaining
        """
        if role not in self._role_permissions:
            self._role_permissions[role] = set()
        
        self._role_permissions[role].add(permission)
        return self
    
    def grant_permissions(
        self,
        role: Role,
        permissions: list[Permission],
    ) -> "PermissionBasedPolicy":
        """Grant multiple permissions to role.
        
        Args:
            role: Role to grant permissions to
            permissions: List of permissions to grant
            
        Returns:
            Self for chaining
        """
        for permission in permissions:
            self.grant_permission(role, permission)
        return self
    
    def get_user_permissions(self, auth_context: AuthContext) -> set[Permission]:
        """Get all permissions for user's roles.
        
        Args:
            auth_context: Authenticated user
            
        Returns:
            Set of all permissions granted to user's roles
        """
        permissions = set()
        for role in auth_context.roles:
            if role in self._role_permissions:
                permissions.update(self._role_permissions[role])
        return permissions
    
    def evaluate(self, auth_context: AuthContext, **kwargs) -> bool:
        """Evaluate permission-based authorization.
        
        Args:
            auth_context: Authenticated user
            required_permission: The required Permission (from kwargs)
            
        Returns:
            True if user has required permission
        """
        required_permission = kwargs.get("required_permission")
        
        if required_permission is None:
            raise PolicyEvaluationError("Missing 'required_permission' in policy context")
        
        user_permissions = self.get_user_permissions(auth_context)
        return required_permission in user_permissions


class TimeBasedPolicy(AuthorizationPolicy):
    """Time-based authorization policy.
    
    Checks if token is within valid time window.
    Useful for rate limiting or scheduled access.
    """
    
    def evaluate(self, auth_context: AuthContext, **kwargs) -> bool:
        """Check if token is expired."""
        return not auth_context.is_expired


# Pre-configured policy instances for common scenarios
class PolicyTemplates:
    """Common authorization policy templates."""
    
    @staticmethod
    def admin_only() -> RoleBasedAuthorizationPolicy:
        """Policy: Only admins allowed."""
        policy = RoleBasedAuthorizationPolicy()
        policy.require_role(Role.ADMIN)
        return policy
    
    @staticmethod
    def authenticated_only() -> RoleBasedAuthorizationPolicy:
        """Policy: Any authenticated user allowed."""
        policy = RoleBasedAuthorizationPolicy()
        policy.require_any_role([Role.ADMIN, Role.USER, Role.WORKER])
        return policy
    
    @staticmethod
    def user_or_admin() -> RoleBasedAuthorizationPolicy:
        """Policy: Users or admins allowed."""
        policy = RoleBasedAuthorizationPolicy()
        policy.require_any_role([Role.ADMIN, Role.USER])
        return policy
    
    @staticmethod
    def service_to_service() -> RoleBasedAuthorizationPolicy:
        """Policy: Only service workers allowed."""
        policy = RoleBasedAuthorizationPolicy()
        policy.require_role(Role.WORKER)
        return policy
