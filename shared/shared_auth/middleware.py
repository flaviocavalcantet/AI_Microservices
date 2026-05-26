"""Authorization decorators and middleware for Flask routes.

Provides:
- JWT validation middleware
- Role-based access decorators
- Permission-based decorators
- Resource ownership checks
- Extensible authorization hooks

Design:
- Decorators are composable and chainable
- Fails securely (deny by default)
- Clear error messages for debugging
- Works with Flask's g (request context)
"""

from functools import wraps
from typing import Optional, Callable, List, Any, Dict
from datetime import datetime

from flask import request, g
import logging

from .models import Role, AuthContext
from .jwt_handler import JWTHandler
from .policies import AuthorizationPolicy, RoleBasedAuthorizationPolicy
from .errors import (
    AuthorizationError,
    InsufficientPermissionsError,
    MissingTokenError,
    InvalidTokenError,
    ResourceOwnershipError,
)


logger = logging.getLogger(__name__)


class AuthorizationMiddleware:
    """JWT validation middleware for Flask.
    
    Extracts and validates JWT from request headers.
    Injects AuthContext into g.auth_context for use in route handlers.
    
    Example:
        jwt_handler = create_jwt_handler(...)
        middleware = AuthorizationMiddleware(jwt_handler)
        app.before_request(middleware.validate_token)
    """
    
    def __init__(self, jwt_handler: JWTHandler):
        """Initialize middleware.
        
        Args:
            jwt_handler: Configured JWT handler for validation
        """
        self.jwt_handler = jwt_handler
    
    def validate_token(self) -> Optional[Dict[str, Any]]:
        """Validate JWT from request and inject auth context.
        
        Called by Flask before_request hook.
        Sets g.auth_context if token is present and valid.
        Does NOT require authentication - allows public routes.
        
        Returns:
            None if no token (public route)
            
        Raises:
            AuthorizationError: If token is invalid or expired
        """
        auth_header = request.headers.get("Authorization", "")
        
        # Allow missing token for public routes
        if not auth_header:
            g.auth_context = None
            return None
        
        try:
            # Extract bearer token
            token = self.jwt_handler.extract_bearer_token(auth_header)
            
            # Validate and extract claims
            auth_context = self.jwt_handler.validate_token(token)
            
            # Inject into request context
            g.auth_context = auth_context
            
            logger.debug(f"Token validated for user: {auth_context.user_id}")
            
        except AuthorizationError as e:
            logger.warning(f"Token validation failed: {e.message}")
            g.auth_context = None
            raise
    
    def get_auth_context(self) -> Optional[AuthContext]:
        """Get current auth context from request.
        
        Returns:
            AuthContext if authenticated, None if public request
        """
        return g.get("auth_context")


def require_authenticated(f: Callable) -> Callable:
    """Decorator: Require authentication (any role).
    
    Fails with 401 if no token or invalid token.
    
    Example:
        @app.route('/api/me')
        @require_authenticated
        def get_me():
            auth = g.auth_context
            return {"user_id": auth.user_id}
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_context = g.get("auth_context")
        
        if auth_context is None:
            logger.warning("Access denied: No authentication")
            raise MissingTokenError("Authentication required")
        
        if auth_context.is_expired:
            logger.warning(f"Access denied: Token expired for user {auth_context.user_id}")
            raise AuthorizationError("Token has expired", code="TOKEN_EXPIRED")
        
        logger.debug(f"Authenticated access granted to user: {auth_context.user_id}")
        return f(*args, **kwargs)
    
    return decorated


def require_role(roles: List[Role] | Role) -> Callable:
    """Decorator: Require specific role(s).
    
    Fails with 403 if user lacks required roles.
    
    Args:
        roles: Single Role or list of roles required
    
    Example:
        @app.route('/api/admin')
        @require_role(Role.ADMIN)
        def admin_endpoint():
            ...
        
        @app.route('/api/users')
        @require_role([Role.ADMIN, Role.USER])  # Require any
        def user_endpoint():
            ...
    """
    if isinstance(roles, Role):
        roles = [roles]
    
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            auth_context = g.get("auth_context")
            
            if auth_context is None:
                logger.warning("Access denied: No authentication")
                raise MissingTokenError("Authentication required")
            
            if not auth_context.has_any_role(roles):
                logger.warning(
                    f"Access denied: User {auth_context.user_id} has roles "
                    f"{auth_context.roles}, required: {roles}"
                )
                raise InsufficientPermissionsError(
                    message=f"Requires one of: {', '.join(r.value for r in roles)}",
                    required_roles=[r.value for r in roles],
                )
            
            logger.debug(f"Role check passed for user: {auth_context.user_id}")
            return f(*args, **kwargs)
        
        return decorated
    
    return decorator


def require_all_roles(roles: List[Role]) -> Callable:
    """Decorator: Require all specified roles.
    
    Fails with 403 if user lacks any required role.
    
    Example:
        @app.route('/api/super-admin')
        @require_all_roles([Role.ADMIN, Role.WORKER])
        def super_admin_endpoint():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            auth_context = g.get("auth_context")
            
            if auth_context is None:
                logger.warning("Access denied: No authentication")
                raise MissingTokenError("Authentication required")
            
            if not auth_context.has_all_roles(roles):
                logger.warning(
                    f"Access denied: User {auth_context.user_id} has roles "
                    f"{auth_context.roles}, required all: {roles}"
                )
                raise InsufficientPermissionsError(
                    message=f"Requires all of: {', '.join(r.value for r in roles)}",
                    required_roles=[r.value for r in roles],
                )
            
            logger.debug(f"All roles check passed for user: {auth_context.user_id}")
            return f(*args, **kwargs)
        
        return decorated
    
    return decorator


def require_any_role(roles: List[Role]) -> Callable:
    """Decorator: Require at least one of the specified roles.
    
    Alias for require_role() with list of roles.
    
    Example:
        @app.route('/api/team')
        @require_any_role([Role.ADMIN, Role.USER])
        def team_endpoint():
            ...
    """
    return require_role(roles)


def require_permission(permission_checker: Callable[[AuthContext], bool]) -> Callable:
    """Decorator: Require custom permission check.
    
    Allows fine-grained authorization via callable.
    
    Args:
        permission_checker: Callable that takes AuthContext and returns bool
    
    Example:
        def is_job_owner(auth_context):
            job_id = request.view_args.get('job_id')
            return check_ownership(auth_context.user_id, job_id)
        
        @app.route('/jobs/<job_id>')
        @require_permission(is_job_owner)
        def update_job(job_id):
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            auth_context = g.get("auth_context")
            
            if auth_context is None:
                logger.warning("Access denied: No authentication")
                raise MissingTokenError("Authentication required")
            
            try:
                if not permission_checker(auth_context):
                    logger.warning(
                        f"Access denied: Permission check failed for "
                        f"user {auth_context.user_id}"
                    )
                    raise InsufficientPermissionsError(
                        message="Permission denied"
                    )
            except InsufficientPermissionsError:
                raise
            except Exception as e:
                logger.error(f"Permission check error: {str(e)}", exc_info=True)
                raise InsufficientPermissionsError(
                    message="Permission check failed"
                )
            
            logger.debug(f"Permission check passed for user: {auth_context.user_id}")
            return f(*args, **kwargs)
        
        return decorated
    
    return decorator


def require_resource_ownership(
    resource_id_param: str = "resource_id",
    owner_id_getter: Optional[Callable[[str], str]] = None,
    allow_admin: bool = True,
) -> Callable:
    """Decorator: Require resource ownership.
    
    Checks if authenticated user is the resource owner.
    
    Args:
        resource_id_param: Name of route parameter containing resource ID
        owner_id_getter: Optional callable(resource_id) -> owner_id
                        If not provided, assumes owner_id == resource_id
        allow_admin: If True, admins bypass ownership check
    
    Example:
        @app.route('/jobs/<resource_id>')
        @require_resource_ownership('resource_id')
        def get_job(resource_id):
            ...
        
        # With custom owner lookup:
        def get_job_owner(job_id):
            job = Job.find_by_id(job_id)
            return job.owner_id
        
        @app.route('/jobs/<job_id>')
        @require_resource_ownership('job_id', owner_id_getter=get_job_owner)
        def update_job(job_id):
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            auth_context = g.get("auth_context")
            
            if auth_context is None:
                logger.warning("Access denied: No authentication")
                raise MissingTokenError("Authentication required")
            
            # Allow admin bypass
            if allow_admin and auth_context.is_admin():
                logger.debug(f"Admin bypass for resource ownership check")
                return f(*args, **kwargs)
            
            # Get resource ID from route params
            resource_id = kwargs.get(resource_id_param)
            if not resource_id:
                logger.error(
                    f"Resource ownership check: Missing parameter '{resource_id_param}'"
                )
                raise InsufficientPermissionsError("Invalid request")
            
            # Get owner ID
            if owner_id_getter:
                try:
                    owner_id = owner_id_getter(resource_id)
                except Exception as e:
                    logger.error(f"Error getting resource owner: {str(e)}", exc_info=True)
                    raise InsufficientPermissionsError("Unable to verify ownership")
            else:
                owner_id = resource_id
            
            # Check ownership
            if auth_context.user_id != owner_id:
                logger.warning(
                    f"Access denied: User {auth_context.user_id} is not owner of "
                    f"resource {resource_id} (owner: {owner_id})"
                )
                raise ResourceOwnershipError(resource_id=resource_id)
            
            logger.debug(
                f"Ownership check passed: user {auth_context.user_id} owns {resource_id}"
            )
            return f(*args, **kwargs)
        
        return decorated
    
    return decorator


def require_policy(policy: AuthorizationPolicy, **policy_kwargs) -> Callable:
    """Decorator: Require policy evaluation.
    
    Evaluates an AuthorizationPolicy for fine-grained authorization.
    
    Args:
        policy: Authorization policy to evaluate
        **policy_kwargs: Additional context passed to policy.evaluate()
    
    Example:
        owner_policy = ResourceOwnershipPolicy()
        
        @app.route('/jobs/<job_id>')
        @require_policy(
            owner_policy,
            resource_owner_id=lambda jid: get_job(jid).owner_id
        )
        def update_job(job_id):
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            auth_context = g.get("auth_context")
            
            if auth_context is None:
                logger.warning("Access denied: No authentication")
                raise MissingTokenError("Authentication required")
            
            # Resolve callable arguments
            resolved_kwargs = {}
            for key, value in policy_kwargs.items():
                if callable(value):
                    try:
                        resolved_kwargs[key] = value(**kwargs)
                    except Exception as e:
                        logger.error(f"Error resolving policy arg '{key}': {str(e)}")
                        raise InsufficientPermissionsError("Authorization check failed")
                else:
                    resolved_kwargs[key] = value
            
            # Evaluate policy
            try:
                policy.assert_authorized(auth_context, **resolved_kwargs)
            except InsufficientPermissionsError:
                raise
            except Exception as e:
                logger.error(f"Policy evaluation error: {str(e)}", exc_info=True)
                raise InsufficientPermissionsError("Authorization check failed")
            
            logger.debug(f"Policy check passed for user: {auth_context.user_id}")
            return f(*args, **kwargs)
        
        return decorated
    
    return decorator


def optional_authentication(f: Callable) -> Callable:
    """Decorator: Allow optional authentication.
    
    Route is accessible to both authenticated and unauthenticated users.
    Use when you want to treat authenticated and anonymous users differently.
    
    Example:
        @app.route('/jobs')
        @optional_authentication
        def list_jobs():
            auth = g.get('auth_context')
            if auth:
                return get_my_jobs(auth.user_id)
            else:
                return get_public_jobs()
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # auth_context may be None (public route)
        # Caller should check: if g.auth_context: ...
        return f(*args, **kwargs)
    
    return decorated


def get_auth_context() -> Optional[AuthContext]:
    """Get current request's auth context.
    
    Returns:
        AuthContext if authenticated, None if public request
        
    Example:
        @app.route('/me')
        @optional_authentication
        def get_me():
            auth = get_auth_context()
            if not auth:
                return {"message": "Anonymous"}, 200
            return {"user_id": auth.user_id}
    """
    return g.get("auth_context")


def assert_authenticated() -> AuthContext:
    """Assert authentication is present, return auth context.
    
    Use in route handlers to get auth context with guaranteed non-None.
    
    Returns:
        AuthContext
        
    Raises:
        MissingTokenError: If not authenticated
        
    Example:
        @app.route('/me')
        @require_authenticated
        def get_me():
            auth = assert_authenticated()
            return {"user_id": auth.user_id}
    """
    auth_context = g.get("auth_context")
    
    if auth_context is None:
        raise MissingTokenError("Authentication required")
    
    return auth_context
