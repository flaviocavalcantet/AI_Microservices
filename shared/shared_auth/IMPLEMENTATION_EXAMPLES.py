"""Role-Based Authorization Implementation Examples

This document provides practical examples of implementing RBAC in Flask services.

Examples cover:
1. Setting up JWT validation middleware
2. Protecting routes with role decorators
3. Resource ownership checks
4. Custom authorization policies
5. Error handling
6. Integration with dependency injection
"""

# =============================================================================
# EXAMPLE 1: Application Factory with Authorization Setup
# =============================================================================

"""
File: services/api_service/src/presentation/app.py
"""

from flask import Flask
from shared.shared_auth import (
    create_jwt_handler,
    AuthorizationMiddleware,
    register_error_handlers,
)
from shared.shared_config import SharedSettings

def create_app(config: SharedSettings) -> Flask:
    """Create Flask application with authorization."""
    app = Flask(__name__)
    
    # Configure JWT handler
    jwt_handler = create_jwt_handler(
        algorithm=config.JWT_ALGORITHM,
        secret_or_key=config.JWT_SECRET_KEY,
        issuer=config.JWT_ISSUER,
        audience=config.JWT_AUDIENCE,
    )
    
    # Setup authorization middleware
    auth_middleware = AuthorizationMiddleware(jwt_handler)
    app.before_request(auth_middleware.validate_token)
    
    # Register error handlers for authorization errors
    register_error_handlers(app)
    
    # Register blueprints
    from .routes.v1.jobs import jobs_bp
    from .routes.v1.users import users_bp
    
    app.register_blueprint(jobs_bp)
    app.register_blueprint(users_bp)
    
    return app


# =============================================================================
# EXAMPLE 2: Error Handler for Authorization Errors
# =============================================================================

"""
File: services/api_service/src/presentation/middleware/auth_errors.py
"""

from flask import Flask, jsonify
from shared.shared_auth.errors import (
    AuthorizationError,
    InsufficientPermissionsError,
    MissingTokenError,
    InvalidTokenError,
    TokenExpiredError,
)


def register_error_handlers(app: Flask) -> None:
    """Register authorization error handlers."""
    
    @app.errorhandler(MissingTokenError)
    def handle_missing_token(error):
        return jsonify({
            "error": "UNAUTHORIZED",
            "message": error.message,
            "code": error.code,
        }), 401
    
    @app.errorhandler(InvalidTokenError)
    def handle_invalid_token(error):
        return jsonify({
            "error": "UNAUTHORIZED",
            "message": error.message,
            "code": error.code,
        }), 401
    
    @app.errorhandler(TokenExpiredError)
    def handle_token_expired(error):
        return jsonify({
            "error": "UNAUTHORIZED",
            "message": "Token has expired",
            "code": "TOKEN_EXPIRED",
        }), 401
    
    @app.errorhandler(InsufficientPermissionsError)
    def handle_insufficient_permissions(error):
        return jsonify({
            "error": "FORBIDDEN",
            "message": error.message,
            "code": error.code,
            "details": error.details,
        }), 403
    
    @app.errorhandler(AuthorizationError)
    def handle_authorization_error(error):
        return jsonify(error.to_dict()), error.status_code


# =============================================================================
# EXAMPLE 3: Protected Routes - Role-Based Access
# =============================================================================

"""
File: services/api_service/src/presentation/routes/v1/jobs/controller.py
"""

from flask import Blueprint, request, g, jsonify
from shared.shared_auth import (
    Role,
    require_authenticated,
    require_role,
    require_all_roles,
    get_auth_context,
    assert_authenticated,
)
from shared.shared_logging import get_logger

logger = get_logger(__name__)

jobs_bp = Blueprint("jobs", __name__, url_prefix="/api/v1/jobs")


# Route 1: List jobs (any authenticated user)
@jobs_bp.route("", methods=["GET"])
@require_authenticated
def list_jobs():
    """List all jobs (authenticated users only)."""
    auth = assert_authenticated()
    
    # Business logic: filter jobs based on user role
    if auth.is_admin():
        jobs = get_all_jobs()  # Admin sees everything
    else:
        jobs = get_user_jobs(auth.user_id)  # Users see their own jobs
    
    logger.info(f"Listed {len(jobs)} jobs for user {auth.user_id}")
    return jsonify({"data": jobs}), 200


# Route 2: Create job (only users and admins)
@jobs_bp.route("", methods=["POST"])
@require_role([Role.USER, Role.ADMIN])
def create_job():
    """Create new job (users and admins only)."""
    auth = assert_authenticated()
    data = request.get_json()
    
    # Create job with current user as owner
    job = create_job_use_case(
        name=data["name"],
        owner_id=auth.user_id,
        # ... other fields
    )
    
    logger.info(f"Job {job.id} created by user {auth.user_id}")
    return jsonify({"data": job}), 201


# Route 3: Delete job (admin only)
@jobs_bp.route("/<job_id>", methods=["DELETE"])
@require_role(Role.ADMIN)
def delete_job(job_id):
    """Delete job (admin only)."""
    auth = assert_authenticated()
    
    delete_job_use_case(job_id)
    
    logger.info(f"Job {job_id} deleted by admin {auth.user_id}")
    return "", 204


# Route 4: Get job (any authenticated user, check ownership)
@jobs_bp.route("/<job_id>", methods=["GET"])
@require_authenticated
def get_job(job_id):
    """Get job by ID (user must own or be admin)."""
    auth = assert_authenticated()
    job = get_job_by_id(job_id)
    
    # Authorization: Admin can see all, users see their own
    if not auth.is_admin() and job.owner_id != auth.user_id:
        logger.warning(f"Access denied: user {auth.user_id} cannot access job {job_id}")
        raise InsufficientPermissionsError("Not authorized to access this resource")
    
    return jsonify({"data": job}), 200


# =============================================================================
# EXAMPLE 4: Resource Ownership Decorator
# =============================================================================

"""
File: services/api_service/src/presentation/routes/v1/jobs/routes.py
"""

from shared.shared_auth import require_resource_ownership
from shared.shared_auth.errors import ResourceOwnershipError


def get_job_owner(job_id: str) -> str:
    """Get owner ID of a job."""
    job = get_job_by_id(job_id)
    if not job:
        raise ResourceOwnershipError(resource_id=job_id)
    return job.owner_id


@jobs_bp.route("/<job_id>", methods=["PUT"])
@require_resource_ownership(
    resource_id_param="job_id",
    owner_id_getter=get_job_owner,
    allow_admin=True,
)
def update_job(job_id):
    """Update job (owner or admin only)."""
    auth = assert_authenticated()
    data = request.get_json()
    
    job = update_job_use_case(job_id, **data)
    
    logger.info(f"Job {job_id} updated by {auth.user_id}")
    return jsonify({"data": job}), 200


# =============================================================================
# EXAMPLE 5: Custom Authorization Policies
# =============================================================================

"""
File: services/api_service/src/presentation/routes/v1/jobs/policies.py
"""

from shared.shared_auth import (
    AuthorizationPolicy,
    AuthContext,
    Role,
    InsufficientPermissionsError,
)


class JobCreationPolicy(AuthorizationPolicy):
    """Custom policy: User can create jobs if not exceeded quota."""
    
    def __init__(self, max_jobs_per_user: int = 100):
        self.max_jobs_per_user = max_jobs_per_user
    
    def evaluate(self, auth_context: AuthContext, **kwargs) -> bool:
        """Check if user can create job."""
        # Admins have no quota
        if auth_context.is_admin():
            return True
        
        # Check job count for user
        job_count = count_user_jobs(auth_context.user_id)
        return job_count < self.max_jobs_per_user


# Usage in route:
job_creation_policy = JobCreationPolicy(max_jobs_per_user=100)

@jobs_bp.route("", methods=["POST"])
@require_policy(job_creation_policy)
def create_job():
    """Create job (with quota check)."""
    # ... implementation


# =============================================================================
# EXAMPLE 6: Multi-Service Authorization
# =============================================================================

"""
File: services/ai_worker/src/presentation/routes/tasks/controller.py

AI Worker accepts tasks from API Service (service-to-service communication).
Auth context identifies calling service, not end user.
"""

from shared.shared_auth import Role, require_role

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api/v1/tasks")


@tasks_bp.route("", methods=["POST"])
@require_role(Role.WORKER)
def create_task():
    """Create task (only other services allowed).
    
    This endpoint is called by api-service with a service JWT token
    that has Role.WORKER. End users cannot call this directly.
    """
    auth = assert_authenticated()
    data = request.get_json()
    
    # Service principal identifies calling service
    logger.info(f"Task created by service: {auth.user_id}")
    
    task = create_task_use_case(**data)
    return jsonify({"data": task}), 201


# =============================================================================
# EXAMPLE 7: Complex Authorization with Multiple Policies
# =============================================================================

"""
File: services/api_service/src/presentation/routes/v1/jobs/advanced.py

Example: Allow access if:
- User is admin, OR
- User is owner AND job status != 'archived'
"""

from shared.shared_auth import (
    AuthorizationPolicy,
    CompositeAuthorizationPolicy,
    ResourceOwnershipPolicy,
    require_policy,
)


class ArchiveJobPolicy(AuthorizationPolicy):
    """Check if job is not archived."""
    
    def evaluate(self, auth_context, **kwargs) -> bool:
        job_id = kwargs.get("job_id")
        job = get_job_by_id(job_id)
        return job.status != "archived"


# Compose policies: Admin OR (Owner AND NotArchived)
advanced_policy = CompositeAuthorizationPolicy(mode="or")
advanced_policy.add(AuthorizationPolicy())  # Admin bypass
advanced_policy.add(
    CompositeAuthorizationPolicy(mode="and")
    .add(ResourceOwnershipPolicy())
    .add(ArchiveJobPolicy())
)


@jobs_bp.route("/<job_id>/execute", methods=["POST"])
@require_policy(
    advanced_policy,
    job_id=lambda job_id: job_id,
    resource_owner_id=lambda job_id: get_job_by_id(job_id).owner_id,
)
def execute_job(job_id):
    """Execute job (admin or owner with non-archived job)."""
    auth = assert_authenticated()
    job = execute_job_use_case(job_id)
    return jsonify({"data": job}), 200


# =============================================================================
# EXAMPLE 8: Getting Auth Context Without Decorator
# =============================================================================

"""
Sometimes you need auth context in a use case or helper function.
"""

from shared.shared_auth import get_auth_context, assert_authenticated


@jobs_bp.route("/my-jobs", methods=["GET"])
def list_my_jobs():
    """List only current user's jobs (using get_auth_context)."""
    auth = get_auth_context()
    
    if not auth:
        return jsonify({"error": "Authentication required"}), 401
    
    jobs = get_user_jobs(auth.user_id)
    return jsonify({"data": jobs}), 200


# Or in use cases:
class ListJobsUseCase:
    def execute(self):
        auth = assert_authenticated()
        return get_user_jobs(auth.user_id)


# =============================================================================
# EXAMPLE 9: Service Container Integration
# =============================================================================

"""
File: services/api_service/src/container.py

Inject authorization policies into use cases via dependency injection.
"""

from shared.shared_auth import RoleBasedAuthorizationPolicy, Role


class ServiceContainer:
    def __init__(self, config):
        self.config = config
        self._services = {}
    
    def setup_authorization(self):
        """Setup authorization policies."""
        
        # Policy for job creation
        create_job_policy = RoleBasedAuthorizationPolicy()
        create_job_policy.require_any_role([Role.ADMIN, Role.USER])
        
        self.register("create_job_policy", create_job_policy)
        
        # Policy for admin operations
        admin_policy = RoleBasedAuthorizationPolicy()
        admin_policy.require_role(Role.ADMIN)
        
        self.register("admin_policy", admin_policy)
    
    def setup_use_cases(self):
        """Setup use cases with policies."""
        
        def create_list_jobs_use_case():
            policy = self.get("create_job_policy")
            repo = self.get("job_repository")
            return ListJobsUseCase(repo, policy)
        
        self.register("list_jobs_use_case", create_list_jobs_use_case)


# =============================================================================
# EXAMPLE 10: Testing Authorization
# =============================================================================

"""
File: tests/unit/api_service/presentation/test_jobs_authorization.py
"""

import pytest
from flask import Flask
from shared.shared_auth import (
    AuthContext,
    Role,
    HMACJWTHandler,
    AuthorizationMiddleware,
)
from datetime import datetime, timedelta


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    
    jwt_handler = HMACJWTHandler(
        secret_key="test-secret-key",
        issuer="test-issuer",
        audience="test-audience",
    )
    
    auth_middleware = AuthorizationMiddleware(jwt_handler)
    app.before_request(auth_middleware.validate_token)
    
    return app


@pytest.fixture
def admin_auth_context():
    """Create admin auth context."""
    return AuthContext(
        user_id="admin-123",
        roles=[Role.ADMIN],
        session_id="session-123",
        issued_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=1),
        jti="jti-123",
        email="admin@example.com",
    )


@pytest.fixture
def user_auth_context():
    """Create user auth context."""
    return AuthContext(
        user_id="user-123",
        roles=[Role.USER],
        session_id="session-456",
        issued_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=1),
        jti="jti-456",
        email="user@example.com",
    )


def test_admin_can_delete_job(app, admin_auth_context):
    """Test that admin can delete any job."""
    with app.test_request_context():
        from flask import g
        g.auth_context = admin_auth_context
        
        # Call route handler or use case
        # Should not raise InsufficientPermissionsError


def test_user_cannot_delete_job(app, user_auth_context):
    """Test that regular user cannot delete jobs."""
    with app.test_request_context():
        from flask import g
        g.auth_context = user_auth_context
        
        # Call route handler or use case
        # Should raise InsufficientPermissionsError


def test_no_auth_returns_401(app):
    """Test that unauthenticated request returns 401."""
    with app.test_request_context():
        # Call route handler
        # Should return 401


if __name__ == "__main__":
    print("See examples above for RBAC implementation patterns.")
