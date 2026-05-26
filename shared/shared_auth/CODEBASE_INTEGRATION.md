"""RBAC Integration with Existing Codebase

How the new shared_auth module integrates with your existing services.
"""

# =============================================================================
# FILE STRUCTURE
# =============================================================================

"""
Before RBAC:
───────────
shared/
  ├─ shared_config/
  ├─ shared_events/
  ├─ shared_http/
  ├─ shared_kernel/
  ├─ shared_logging/
  └─ shared_utils/

After RBAC:
──────────
shared/
  ├─ shared_auth/                    ← NEW
  │  ├─ __init__.py                  ← Exports: Role, AuthContext, decorators
  │  ├─ models.py                    ← Domain: Role, AuthContext, Permission
  │  ├─ errors.py                    ← Errors: AuthorizationError, etc.
  │  ├─ jwt_handler.py               ← JWT: HMACJWTHandler, RSAJWTHandler
  │  ├─ policies.py                  ← Policies: Authorization logic
  │  ├─ middleware.py                ← Decorators: @require_role, etc.
  │  ├─ requirements.txt              ← PyJWT>=2.8.0
  │  ├─ README.md                    ← Quick reference
  │  ├─ ARCHITECTURE.md              ← System design
  │  ├─ BEST_PRACTICES.md            ← Patterns and anti-patterns
  │  ├─ IMPLEMENTATION_EXAMPLES.py   ← Code examples
  │  ├─ INTEGRATION_GUIDE.md         ← How to integrate
  │  └─ IMPLEMENTATION_SUMMARY.txt   ← Overview
  │
  ├─ shared_config/
  │  └─ src/
  │      └─ settings.py              ← Already has JWT config
  │
  ├─ shared_logging/
  │  └─ src/
  │      └─ logging.py               ← Works with auth logging
  │
  └─ ... (others unchanged)
"""

# =============================================================================
# INTEGRATION WITH EXISTING LAYERS
# =============================================================================

"""
SHARED_CONFIG INTEGRATION:
──────────────────────────

✓ SharedSettings already includes JWT config:
  - JWT_SECRET_KEY
  - JWT_ALGORITHM
  - JWT_ISSUER
  - JWT_AUDIENCE
  - JWT_EXPIRATION_HOURS

✓ No changes needed - already compatible


SHARED_LOGGING INTEGRATION:
───────────────────────────

✓ Authorization events logged automatically:
  logger = get_logger(__name__)
  logger.warning(f"Authorization failed: {reason}")

✓ Middleware integrates with request logging:
  - User ID extracted from JWT → added to log context
  - All auth events have consistent format
  - Correlation ID tracked across requests

✓ Example log entry:
  {
    "timestamp": "2026-05-26T10:30:45Z",
    "level": "WARNING",
    "service": "api-service",
    "user_id": "user-123",
    "event": "authorization_failure",
    "error": "InsufficientPermissionsError",
    "endpoint": "/api/v1/jobs/job-123",
    "method": "DELETE",
    "required_roles": ["admin"],
    "user_roles": ["user"],
    "correlation_id": "corr-123"
  }


SERVICES INTEGRATION:
─────────────────────

services/api_service/
├─ src/
│  ├─ presentation/
│  │  ├─ app.py                ← Setup: Import create_jwt_handler, middleware
│  │  ├─ middleware/
│  │  │  └─ auth_errors.py     ← NEW: Error handlers
│  │  └─ routes/
│  │      ├─ v1/jobs/
│  │      │  └─ controller.py  ← Add: @require_role, @require_authenticated
│  │      └─ v1/users/
│  │         └─ controller.py  ← Add: @require_authenticated, ownership checks
│  │
│  ├─ application/
│  │  └─ use_cases/
│  │      └─ (no changes needed)
│  │
│  └─ infrastructure/
│     └─ (no changes needed)
│
└─ requirements.txt  ← Add: -e ../../../shared/shared_auth


services/auth_service/
├─ src/
│  ├─ infrastructure/
│  │  ├─ security/
│  │  │  └─ jwt_service.py     ← Extend: Issue tokens with claims
│  │  │
│  │  └─ repositories/
│  │     └─ (store roles per user)
│  │
│  └─ presentation/
│     ├─ routes/
│     │  └─ auth_routes.py      ← Issue: JWT with roles claim
│     │
│     └─ (no auth decorator needed here)
│
└─ requirements.txt  ← Add: -e ../../../shared/shared_auth


services/ai_worker/
├─ src/
│  ├─ presentation/
│  │  ├─ routes/
│  │  │  ├─ v1/tasks/
│  │  │  │  └─ controller.py    ← Add: @require_role(Role.WORKER)
│  │  │  └─ health.py           ← Public endpoint (no auth)
│  │  │
│  │  └─ (service-to-service only)
│  │
│  └─ (no auth_service changes needed)
│
└─ requirements.txt  ← Add: -e ../../../shared/shared_auth


services/notification_service/
└─ (similar to ai_worker - service-to-service only)
"""

# =============================================================================
# CODE CHANGES REQUIRED (Per Service)
# =============================================================================

"""
API_SERVICE CHANGES:
────────────────────

1. src/presentation/app.py (Add ~30 lines)
   
   from shared.shared_auth import (
       create_jwt_handler,
       AuthorizationMiddleware,
   )
   
   def create_app(config):
       app = Flask(__name__)
       
       # Setup JWT
       jwt_handler = create_jwt_handler(...)
       auth_middleware = AuthorizationMiddleware(jwt_handler)
       app.before_request(auth_middleware.validate_token)
       
       # Register error handlers
       register_error_handlers(app)
       
       # Register blueprints
       from .routes.v1.jobs import jobs_bp
       app.register_blueprint(jobs_bp)
       
       return app

2. src/presentation/middleware/auth_errors.py (NEW - ~50 lines)
   
   from shared.shared_auth.errors import (
       AuthorizationError,
       InsufficientPermissionsError,
   )
   
   def register_error_handlers(app):
       @app.errorhandler(AuthorizationError)
       def handle_auth_error(error):
           return {"error": error.code}, error.status_code

3. src/presentation/routes/v1/jobs/controller.py (Add decorators)
   
   from shared.shared_auth import (
       Role,
       require_authenticated,
       require_role,
       assert_authenticated,
   )
   
   @jobs_bp.route("", methods=["GET"])
   @require_authenticated          # ← Add this
   def list_jobs():
       auth = assert_authenticated()
       ...
   
   @jobs_bp.route("/<job_id>", methods=["DELETE"])
   @require_role(Role.ADMIN)       # ← Add this
   def delete_job(job_id):
       ...

4. requirements.txt
   
   Add: -e ../../../shared/shared_auth

TOTAL CHANGES: ~120 lines of code


AUTH_SERVICE CHANGES:
─────────────────────

1. src/infrastructure/security/jwt_service.py
   
   BEFORE (stub):
     def issue_access_token(self, subject, claims=None):
       raise NotImplementedError("JWT issuing is not implemented")
   
   AFTER (implement):
     def issue_access_token(self, subject, claims=None):
       payload = {
           "sub": subject,
           "iat": datetime.utcnow(),
           "exp": datetime.utcnow() + timedelta(seconds=900),
           "roles": claims.get("roles", []),
           ...
       }
       return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

2. No route changes needed (no user-facing auth endpoints yet)

3. requirements.txt
   
   Add: -e ../../../shared/shared_auth

TOTAL CHANGES: ~50 lines of code


AI_WORKER & NOTIFICATION_SERVICE CHANGES:
──────────────────────────────────────────

1. src/presentation/app.py (Same as api_service ~30 lines)
   
   jwt_handler = create_jwt_handler(...)
   auth_middleware = AuthorizationMiddleware(jwt_handler)
   app.before_request(auth_middleware.validate_token)

2. src/presentation/routes/v1/tasks/controller.py
   
   @app.route('/api/v1/tasks', methods=['POST'])
   @require_role(Role.WORKER)              # ← Add this
   def create_task():
       auth = assert_authenticated()
       # auth.user_id is "api-service" (service principal)
       ...

3. requirements.txt
   
   Add: -e ../../../shared/shared_auth

TOTAL CHANGES: ~80 lines of code


TOTAL CHANGES ACROSS ALL SERVICES:
───────────────────────────────────
Code: ~250 lines (mostly decorators and setup)
Configuration: 0 lines (already present)
Dependencies: 1 line per service
"""

# =============================================================================
# TESTING INTEGRATION
# =============================================================================

"""
TEST STRUCTURE:
───────────────

tests/
├─ unit/
│  ├─ api_service/
│  │  └─ presentation/
│  │     ├─ test_authorization.py     ← NEW: Auth-specific tests
│  │     └─ routes/
│  │        └─ test_jobs.py           ← MODIFIED: Add auth test cases
│  │
│  ├─ auth_service/
│  │  └─ application/
│  │     └─ test_jwt_service.py       ← MODIFIED: JWT issuance tests
│  │
│  └─ shared/
│     └─ test_authorization.py        ← NEW: Shared auth tests
│
└─ integration/
   └─ test_auth_flow.py               ← NEW: Full auth flow tests


TEST EXAMPLES:
──────────────

1. Unit test with auth context fixture

   @pytest.fixture
   def admin_context():
       return AuthContext(...)
   
   def test_admin_can_delete_job(admin_context):
       with app.test_request_context():
           g.auth_context = admin_context
           response = delete_job("job-123")
           assert response.status_code == 204

2. Integration test with JWT token

   def test_delete_job_with_admin_token():
       token = generate_jwt_token(roles=[Role.ADMIN])
       response = client.delete(
           '/jobs/job-123',
           headers={'Authorization': f'Bearer {token}'}
       )
       assert response.status_code == 204

3. Error case

   def test_user_cannot_delete_job():
       token = generate_jwt_token(roles=[Role.USER])
       response = client.delete(
           '/jobs/job-123',
           headers={'Authorization': f'Bearer {token}'}
       )
       assert response.status_code == 403
"""

# =============================================================================
# MIGRATION PATH (Week-by-week)
# =============================================================================

"""
WEEK 1: Setup & Foundation
──────────────────────────

Day 1:
  □ Review RBAC documentation (README.md, ARCHITECTURE.md)
  □ Review implementation examples
  □ Understand roles and policies

Day 2-3:
  □ Setup JWT handler in api_service/src/presentation/app.py
  □ Register middleware and error handlers
  □ Run tests to verify setup

Day 4-5:
  □ Protect health check and public endpoints
  □ Test that public routes still work
  □ Setup logging

Day 6-7:
  □ Review and planning for next week
  □ Team training on RBAC concepts


WEEK 2: Protect Critical Endpoints
───────────────────────────────────

Day 1-2:
  □ Add @require_authenticated to user-facing routes
  □ Test that unauthenticated requests get 401
  □ Update test suite

Day 3-4:
  □ Add @require_role decorators to admin routes
  □ Add error responses
  □ Test role-based access

Day 5-6:
  □ Add resource ownership checks
  □ Test user can't access others' resources
  □ Admin can access all

Day 7:
  □ Code review
  □ Security review


WEEK 3: Extend to All Services
───────────────────────────────

Day 1-2:
  □ Apply same patterns to ai_worker
  □ Setup service-to-service auth (WORKER role)
  □ Test service-to-service calls

Day 3-4:
  □ Apply same patterns to notification_service
  □ Test end-to-end workflows

Day 5-6:
  □ Update auth_service to issue tokens with roles
  □ Test full auth flow (login → token → api call)

Day 7:
  □ Code review
  □ Planning for production


WEEK 4: Production Readiness
─────────────────────────────

Day 1-2:
  □ Switch to RS256 (production signing)
  □ Generate RSA key pair
  □ Distribute public key

Day 3-4:
  □ Setup monitoring and logging
  □ Test token expiration handling
  □ Test rate limiting (if using)

Day 5-6:
  □ Security audit
  □ Performance testing
  □ Documentation review

Day 7:
  □ Deployment planning
  □ Go/no-go decision
"""

# =============================================================================
# BACKWARDS COMPATIBILITY
# =============================================================================

"""
✓ FULLY BACKWARDS COMPATIBLE

No breaking changes to existing code:
- Services can be updated one at a time
- Unauthenticated requests to public routes still work
- Authentication is opt-in via decorators
- Existing error handling still works
- Logging integration seamless

Migration Strategy:
1. Deploy RBAC to all services (no decorators yet)
2. Add decorators to critical endpoints first
3. Gradually add decorators to all endpoints
4. At any point, rollback by removing decorators

Zero downtime migration possible.
"""

# =============================================================================
# DEPLOYMENT CHECKLIST
# =============================================================================

"""
PRE-DEPLOYMENT:
───────────────

Code:
  □ All changes reviewed and tested
  □ No hardcoded secrets
  □ Error handling comprehensive
  □ Logging setup verified

Configuration:
  □ JWT_ALGORITHM = "RS256"
  □ JWT_SECRET_KEY = (public key from vault)
  □ JWT_ISSUER set correctly
  □ JWT_AUDIENCE set correctly

Operations:
  □ RSA keys generated and secured
  □ Private key in secure vault
  □ Public key in all services
  □ Monitoring alerts configured
  □ Runbooks created

Testing:
  □ Unit tests passing
  □ Integration tests passing
  □ Manual smoke tests
  □ Load testing with auth
  □ Failover testing

Documentation:
  □ API docs updated with auth requirements
  □ Troubleshooting guide published
  □ Team trained on RBAC
  □ On-call procedures updated


DEPLOYMENT:
───────────

1. Deploy auth-service first (issues tokens)
2. Deploy api-service with RBAC
3. Deploy ai-worker with RBAC
4. Deploy notification-service with RBAC
5. Verify all services communicating
6. Monitor auth failures
7. Gradual rollout if needed


POST-DEPLOYMENT:
────────────────

□ Monitor 401/403 error rates
□ Check token validation latency
□ Verify service-to-service calls working
□ Monitor for any issues
□ Gradually increase audit logging
□ Plan for future enhancements
"""

if __name__ == "__main__":
    print("See this document for integration details with existing codebase")
