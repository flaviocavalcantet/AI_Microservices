"""Integration Guide: Adding RBAC to Flask Services

Step-by-step guide to integrate the shared_auth module into your services.

Steps:
1. Configuration
2. Setup JWT handler
3. Register middleware
4. Protect routes
5. Test authorization
6. Monitor authorization
"""

# =============================================================================
# STEP 1: Configuration
# =============================================================================

"""
Update SharedSettings in shared/shared_config/src/settings.py

Ensure these JWT settings are configured:

    JWT_SECRET_KEY: str = Field(
        default="dev-secret-key-only-for-testing",
        description="Secret key for JWT signing"
    )
    
    JWT_ALGORITHM: str = Field(
        default="HS256",  # or "RS256" for production
        description="Algorithm for JWT signing"
    )
    
    JWT_ISSUER: str = Field(
        default="auth_service",
        description="JWT issuer claim"
    )
    
    JWT_AUDIENCE: str = Field(
        default="ai_platform",
        description="JWT audience claim"
    )
    
    JWT_ACCESS_TOKEN_SECONDS: int = Field(
        default=900,  # 15 minutes
        description="Access token expiration in seconds"
    )

Development:
    JWT_ALGORITHM=HS256
    JWT_SECRET_KEY=dev-secret-key-change-in-production-32-chars-min

Production:
    JWT_ALGORITHM=RS256
    JWT_SECRET_KEY=<paste-public-key-pem>
    # Private key only in auth-service
"""

# =============================================================================
# STEP 2: Setup JWT Handler in Service
# =============================================================================

"""
File: services/api_service/src/presentation/app.py

Add this to your app factory:
"""

from flask import Flask
from shared.shared_auth import (
    create_jwt_handler,
    AuthorizationMiddleware,
)
from shared.shared_config import SharedSettings

def create_app(config: SharedSettings) -> Flask:
    """Create Flask application with JWT authorization."""
    app = Flask(__name__)
    
    # Step 1: Create JWT handler
    jwt_handler = create_jwt_handler(
        algorithm=config.JWT_ALGORITHM,
        secret_or_key=config.JWT_SECRET_KEY,
        issuer=config.JWT_ISSUER,
        audience=config.JWT_AUDIENCE,
    )
    
    # Step 2: Setup middleware
    auth_middleware = AuthorizationMiddleware(jwt_handler)
    
    # Step 3: Register before_request hook
    app.before_request(auth_middleware.validate_token)
    
    # Step 4: Register error handlers
    register_error_handlers(app)
    
    # ... rest of app setup
    return app


def register_error_handlers(app: Flask) -> None:
    """Register handlers for authorization errors."""
    from shared.shared_auth.errors import (
        AuthorizationError,
        InsufficientPermissionsError,
    )
    from flask import jsonify
    
    @app.errorhandler(InsufficientPermissionsError)
    def handle_insufficient_permissions(error):
        return jsonify({
            "error": error.code,
            "message": error.message,
        }), 403
    
    @app.errorhandler(AuthorizationError)
    def handle_authorization_error(error):
        return jsonify({
            "error": error.code,
            "message": error.message,
        }), error.status_code
"""

# =============================================================================
# STEP 3: Register Middleware in Blueprint
# =============================================================================

"""
File: services/api_service/src/presentation/routes/v1/jobs/controller.py

Import decorators in your blueprint:
"""

from flask import Blueprint, request, g, jsonify
from shared.shared_auth import (
    Role,
    require_authenticated,
    require_role,
    assert_authenticated,
    get_auth_context,
)

jobs_bp = Blueprint("jobs", __name__, url_prefix="/api/v1/jobs")


# Public endpoint (no auth required)
@jobs_bp.route("/health", methods=["GET"])
def health():
    """Health check - public."""
    return jsonify({"status": "ok"}), 200


# Authenticated endpoint
@jobs_bp.route("", methods=["GET"])
@require_authenticated
def list_jobs():
    """List jobs (authenticated users only)."""
    auth = assert_authenticated()
    # ... implementation


# Role-restricted endpoint
@jobs_bp.route("/<job_id>", methods=["DELETE"])
@require_role(Role.ADMIN)
def delete_job(job_id):
    """Delete job (admin only)."""
    auth = assert_authenticated()
    # ... implementation
"""

# =============================================================================
# STEP 4: Run Database Migrations (if needed)
# =============================================================================

"""
The RBAC module doesn't require database changes unless you're
storing permissions or roles in the database.

For the standard setup:
- Roles come from JWT claims
- No database changes needed
"""

# =============================================================================
# STEP 5: Testing Authorization
# =============================================================================

"""
File: tests/unit/api_service/presentation/test_authorization.py
"""

import pytest
from flask import Flask
from datetime import datetime, timedelta
from shared.shared_auth import (
    AuthContext,
    Role,
    HMACJWTHandler,
    AuthorizationMiddleware,
    MissingTokenError,
    InsufficientPermissionsError,
)


@pytest.fixture
def app():
    """Create test Flask app."""
    from src.presentation.app import create_app
    from shared.shared_config import SharedSettings
    
    config = SharedSettings(
        FLASK_ENV="test",
        JWT_ALGORITHM="HS256",
        JWT_SECRET_KEY="test-secret-key-32-chars-minimum",
    )
    
    app = create_app(config)
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
    )


def test_unauthenticated_request_fails(app):
    """Test that unauthenticated request returns 401."""
    with app.test_client() as client:
        response = client.get(
            "/api/v1/jobs",
            headers={}  # No Authorization header
        )
        assert response.status_code == 401


def test_admin_can_delete_job(app, admin_auth_context):
    """Test that admin can delete jobs."""
    with app.test_request_context():
        from flask import g
        g.auth_context = admin_auth_context
        
        # Import and call route handler
        from src.presentation.routes.v1.jobs import controller
        response = controller.delete_job("job-123")
        
        # Should succeed (204 No Content)
        assert response[1] == 204


def test_user_cannot_delete_job(app, user_auth_context):
    """Test that regular user cannot delete jobs."""
    with app.test_request_context():
        from flask import g
        g.auth_context = user_auth_context
        
        from src.presentation.routes.v1.jobs import controller
        
        # Should raise InsufficientPermissionsError
        with pytest.raises(InsufficientPermissionsError):
            controller.delete_job("job-123")
"""

# =============================================================================
# STEP 6: Monitoring & Logging
# =============================================================================

"""
The shared_auth module automatically logs:
- Token validation failures
- Authorization failures
- Role checks

To monitor authorization in production:

1. Set up log aggregation (ELK, Datadog, etc.)
2. Create alerts for:
   - High rate of 401/403 errors
   - Repeated failed auth from same IP
   - Unauthorized access attempts to admin endpoints

3. Example queries:
   
   # Failed authorizations
   service=api-service AND (error=UNAUTHORIZED OR error=FORBIDDEN)
   
   # Admin endpoint access
   service=api-service AND role=admin
   
   # Brute force attempts
   error=UNAUTHORIZED AND same_ip_count > 10 in 1m
"""

# =============================================================================
# STEP 7: Deployment Checklist
# =============================================================================

"""
Before deploying to production:

Configuration:
□ JWT_ALGORITHM set to "RS256" (not HS256)
□ JWT_SECRET_KEY contains RSA public key (PEM format)
□ JWT_ISSUER matches auth-service configuration
□ JWT_AUDIENCE set to your audience
□ JWT_ACCESS_TOKEN_SECONDS set appropriately (900 = 15 min)

Code:
□ All sensitive endpoints have @require_authenticated or @require_role
□ Default routes are public (no auth required)
□ Error handlers registered for AuthorizationError
□ Logging configured for authorization events
□ Tests cover authorization paths

Operations:
□ Private key stored securely (not in code/config)
□ Public key distributed to all services
□ Token rotation monitored
□ Authorization events logged and monitored
□ Alerts configured for auth failures

Documentation:
□ API documentation updated with auth requirements
□ Operations runbooks created
□ Security contact information available
□ Incident response plan includes auth issues
"""

# =============================================================================
# STEP 8: Future Enhancements
# =============================================================================

"""
The RBAC module is designed for extensibility. Common enhancements:

1. Custom Roles
   - Extend Role enum with domain-specific roles
   - Update policies to handle new roles

2. Fine-Grained Permissions
   - Use PermissionBasedPolicy for resource:action model
   - Store permissions in database

3. Attribute-Based Access Control (ABAC)
   - Extend policies to check user attributes
   - Example: Department, Team, Location

4. Rate Limiting
   - Combine with Flask-Limiter
   - Rate limit per user, IP, endpoint

5. Token Revocation Lists (TRL)
   - For token revocation without signature revalidation
   - Cache with short TTL

6. Two-Factor Authentication (2FA)
   - Add 2FA flag to JWT claims
   - Require 2FA for sensitive operations

7. Session Management
   - Track session_id in auth_context
   - Implement concurrent session limits

8. Audit Trail
   - Log all authorization decisions
   - Store in separate audit database

Refer to BEST_PRACTICES.md for implementation guidelines.
"""

if __name__ == "__main__":
    print("Follow these steps to integrate RBAC into your services")
