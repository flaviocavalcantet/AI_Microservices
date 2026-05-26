"""Role-Based Authorization (RBAC) - Complete Implementation Guide

Quick Reference & Summary
═════════════════════════════════════════════════════════════════════════════

This document provides a quick reference for the complete RBAC system.
For detailed information, see the other documentation files.

FILES OVERVIEW:
- __init__.py - Package exports
- models.py - Role, AuthContext, Permission domain objects
- errors.py - Authorization-specific exceptions
- jwt_handler.py - JWT token validation and claims extraction
- policies.py - Authorization policies (RBAC, ownership, composite)
- middleware.py - Flask decorators and middleware
- ARCHITECTURE.md - System design and architecture
- IMPLEMENTATION_EXAMPLES.py - Code examples for all patterns
- BEST_PRACTICES.md - Patterns and anti-patterns
- INTEGRATION_GUIDE.md - Step-by-step integration
- requirements.txt - Dependencies (PyJWT)
"""

# =============================================================================
# QUICK START
# =============================================================================

"""
1. INSTALL

Add to your service's requirements.txt:
  -e ../../../shared/shared_auth

Or install PyJWT:
  pip install PyJWT>=2.8.0

2. CONFIGURE

In shared/shared_config/src/settings.py (already configured):
  JWT_SECRET_KEY = "dev-secret-key-only-for-testing"
  JWT_ALGORITHM = "HS256"  # or RS256
  JWT_ISSUER = "auth_service"
  JWT_AUDIENCE = "ai_platform"

3. SETUP IN APP

  from shared.shared_auth import (
    create_jwt_handler,
    AuthorizationMiddleware,
  )
  
  jwt_handler = create_jwt_handler(
    algorithm=config.JWT_ALGORITHM,
    secret_or_key=config.JWT_SECRET_KEY,
    issuer=config.JWT_ISSUER,
    audience=config.JWT_AUDIENCE,
  )
  
  auth_middleware = AuthorizationMiddleware(jwt_handler)
  app.before_request(auth_middleware.validate_token)
  
  # Register error handlers
  from shared.shared_auth.errors import AuthorizationError
  
  @app.errorhandler(AuthorizationError)
  def handle_auth_error(error):
    return {"error": error.code, "message": error.message}, error.status_code

4. PROTECT ROUTES

  from shared.shared_auth import (
    Role,
    require_authenticated,
    require_role,
    require_resource_ownership,
  )
  
  @app.route('/jobs')
  @require_authenticated
  def list_jobs():
    auth = g.auth_context
    return {"user": auth.user_id, "roles": auth.roles}
  
  @app.route('/admin/users')
  @require_role(Role.ADMIN)
  def list_all_users():
    return {"users": []}
  
  @app.route('/jobs/<job_id>')
  @require_resource_ownership('job_id')
  def update_job(job_id):
    return {"updated": True}

5. TEST

  from datetime import datetime, timedelta
  from shared.shared_auth import AuthContext, Role
  
  @pytest.fixture
  def admin_context():
    return AuthContext(
      user_id="admin-1",
      roles=[Role.ADMIN],
      session_id="session-1",
      issued_at=datetime.utcnow(),
      expires_at=datetime.utcnow() + timedelta(hours=1),
      jti="jti-1",
    )
  
  def test_admin_can_delete(admin_context):
    with app.test_request_context():
      g.auth_context = admin_context
      response = delete_job("job-1")
      assert response.status_code == 204
"""

# =============================================================================
# ROLES QUICK REFERENCE
# =============================================================================

"""
ROLE: ADMIN
├─ HTTP 401 Response: No (all endpoints accessible)
├─ HTTP 403 Response: No (never denied)
├─ Can Create: Yes (all resources)
├─ Can Read: Yes (all resources)
├─ Can Update: Yes (all resources)
├─ Can Delete: Yes (all resources)
└─ Can Override Ownership: Yes

ROLE: USER
├─ HTTP 401 Response: No (authenticated)
├─ HTTP 403 Response: Yes (denied for sensitive operations)
├─ Can Create: Yes (own resources)
├─ Can Read: Yes (own resources)
├─ Can Update: Yes (own resources)
├─ Can Delete: No
└─ Can Override Ownership: No

ROLE: WORKER
├─ HTTP 401 Response: No (authenticated service)
├─ HTTP 403 Response: Yes (denied for user operations)
├─ Can Create: Yes (tasks for processing)
├─ Can Read: Yes (assigned tasks)
├─ Can Update: Yes (task state)
├─ Can Delete: No
└─ Can Override Ownership: No (service-to-service)

ANONYMOUS (No Token)
├─ HTTP 401 Response: Yes (if @require_authenticated)
├─ HTTP 403 Response: N/A
├─ Can Access: Public routes only
└─ Public Routes: /health, /docs, login
"""

# =============================================================================
# DECORATOR QUICK REFERENCE
# =============================================================================

"""
@require_authenticated
├─ Fails With: 401 if no token or invalid token
├─ Use For: Any endpoint requiring login
├─ Example:
│   @app.route('/profile')
│   @require_authenticated
│   def get_profile():
│     auth = assert_authenticated()
│     return {"user_id": auth.user_id}

@require_role(Role.ADMIN) or @require_role([Role.ADMIN, Role.USER])
├─ Fails With: 403 if user lacks required role
├─ Requires: @require_authenticated (or applies it)
├─ Use For: Role-specific endpoints
├─ Example:
│   @app.route('/admin')
│   @require_role(Role.ADMIN)
│   def admin_panel():
│     return {"admin_data": [...]}

@require_all_roles([Role.ADMIN, Role.WORKER])
├─ Fails With: 403 if user lacks any role
├─ Use For: Operations requiring multiple roles
├─ Example:
│   @app.route('/super-sensitive')
│   @require_all_roles([Role.ADMIN, Role.WORKER])
│   def super_sensitive():
│     ...

@require_resource_ownership('resource_id', owner_id_getter=..., allow_admin=True)
├─ Fails With: 403 if user is not resource owner
├─ Requires: @require_authenticated
├─ Use For: User-specific resources
├─ Example:
│   @app.route('/jobs/<job_id>')
│   @require_resource_ownership('job_id')
│   def update_job(job_id):
│     ...

@require_permission(checker_func)
├─ Fails With: 403 if checker returns False
├─ Requires: @require_authenticated
├─ Use For: Custom permission checks
├─ Example:
│   def can_edit_job(auth):
│     return auth.user_id == request.form.get('owner_id')
│   
│   @app.route('/jobs/<job_id>')
│   @require_permission(can_edit_job)
│   def edit_job(job_id):
│     ...

@require_policy(policy, **kwargs)
├─ Fails With: 403 if policy evaluation fails
├─ Use For: Complex authorization logic
├─ Example:
│   quota_policy = QuotaPolicy(max=100)
│   
│   @app.route('/resources', methods=['POST'])
│   @require_policy(quota_policy)
│   def create_resource():
│     ...

@optional_authentication
├─ Fails With: Never (route always accessible)
├─ Use For: Mixed anonymous/authenticated endpoints
├─ Example:
│   @app.route('/jobs')
│   @optional_authentication
│   def list_jobs():
│     auth = get_auth_context()
│     if auth:
│       return get_user_jobs(auth.user_id)
│     else:
│       return get_public_jobs()
"""

# =============================================================================
# HTTP STATUS CODES
# =============================================================================

"""
200 OK
└─ Authorization check passed, operation succeeded

201 Created
└─ Resource created successfully with proper authorization

204 No Content
└─ Operation succeeded, no response body

400 Bad Request
└─ Authorization header malformed
├─ Example: "Authorization: Bearertoken" (no space)
└─ Example: "Authorization: Basic ..." (wrong scheme)

401 Unauthorized
├─ Raised By: MissingTokenError, InvalidTokenError, TokenExpiredError
├─ Meaning: User NOT authenticated or token invalid
├─ Causes:
│  - No Authorization header
│  - Token not present in header
│  - Token signature invalid
│  - Token expired
│  - Token issuer/audience mismatch
├─ Client Action: Redirect to login, refresh token, or reauth

403 Forbidden
├─ Raised By: InsufficientPermissionsError, PolicyEvaluationError
├─ Meaning: User authenticated but lacks permissions
├─ Causes:
│  - User role insufficient for operation
│  - User is not resource owner
│  - Authorization policy check failed
│  - Quota exceeded
├─ Client Action: Show "access denied" message

404 Not Found
└─ Resource doesn't exist (not authorization-related)

500 Internal Server Error
├─ Authorization error not caught properly
├─ Should never happen with proper error handling
└─ Indicates bug in authorization logic or configuration
"""

# =============================================================================
# ERROR HANDLING PATTERNS
# =============================================================================

"""
PATTERN 1: Global Error Handler

@app.errorhandler(AuthorizationError)
def handle_auth_error(error):
  logger.warning(f"Authorization failed: {error.message}")
  return jsonify({
    "error": error.code,
    "message": error.message,
  }), error.status_code


PATTERN 2: Specific Error Handlers

@app.errorhandler(MissingTokenError)
def handle_missing_token(error):
  return jsonify({"error": "UNAUTHORIZED"}), 401

@app.errorhandler(InsufficientPermissionsError)
def handle_insufficient_permissions(error):
  return jsonify({
    "error": "FORBIDDEN",
    "required_roles": error.required_roles,
  }), 403


PATTERN 3: Error Wrapper

def with_error_handling(f):
  @wraps(f)
  def wrapper(*args, **kwargs):
    try:
      return f(*args, **kwargs)
    except AuthorizationError as e:
      logger.warning(f"Auth failed: {e}")
      return {"error": e.code}, e.status_code
  return wrapper
"""

# =============================================================================
# COMMON PATTERNS
# =============================================================================

"""
PATTERN 1: Admin-Only Endpoint

@app.route('/admin/settings')
@require_role(Role.ADMIN)
def update_settings():
  auth = assert_authenticated()
  logger.info(f"Admin {auth.user_id} updated settings")
  return {"updated": True}


PATTERN 2: User or Admin with Ownership

@app.route('/jobs/<job_id>')
@require_authenticated
def update_job(job_id):
  auth = assert_authenticated()
  job = get_job(job_id)
  
  # Admins can update any job, users can only update own
  if not auth.is_admin() and job.owner_id != auth.user_id:
    raise InsufficientPermissionsError("Not the job owner")
  
  return update_job_use_case(job_id, request.json)


PATTERN 3: Quota-Based Authorization

quota_policy = QuotaPolicy(max_jobs=100)

@app.route('/jobs', methods=['POST'])
@require_policy(quota_policy)
def create_job():
  auth = assert_authenticated()
  job = create_job_use_case(request.json)
  return {"data": job}, 201


PATTERN 4: Service-to-Service

@app.route('/api/v1/tasks', methods=['POST'])
@require_role(Role.WORKER)
def create_task():
  auth = assert_authenticated()
  # auth.user_id is service_id (e.g., "api-service")
  task = create_task_use_case(request.json)
  return {"data": task}, 201


PATTERN 5: Mixed Anonymous/Authenticated

@app.route('/jobs')
@optional_authentication
def list_jobs():
  auth = get_auth_context()
  
  if auth and auth.is_admin():
    return {"jobs": get_all_jobs()}
  elif auth:
    return {"jobs": get_user_jobs(auth.user_id)}
  else:
    return {"jobs": get_public_jobs()}
"""

# =============================================================================
# TESTING PATTERNS
# =============================================================================

"""
TEST 1: Successful Authorization

def test_admin_can_delete_job(admin_context):
  with app.test_request_context():
    g.auth_context = admin_context
    response = delete_job("job-1")
    assert response.status_code == 204


TEST 2: Failed Authorization

def test_user_cannot_delete_job(user_context):
  with app.test_request_context():
    g.auth_context = user_context
    with pytest.raises(InsufficientPermissionsError):
      delete_job("job-1")


TEST 3: Missing Authentication

def test_unauthenticated_cannot_delete_job():
  with app.test_request_context():
    g.auth_context = None
    with pytest.raises(MissingTokenError):
      delete_job("job-1")


TEST 4: With JWT Token

def test_delete_job_with_token():
  token = generate_jwt_token(user_id="admin-1", roles=[Role.ADMIN])
  
  response = client.delete(
    '/jobs/job-1',
    headers={'Authorization': f'Bearer {token}'}
  )
  
  assert response.status_code == 204
"""

# =============================================================================
# CONFIGURATION FOR DIFFERENT ENVIRONMENTS
# =============================================================================

"""
DEVELOPMENT
───────────

JWT_ALGORITHM = "HS256"
JWT_SECRET_KEY = "dev-secret-key-only-for-testing"
JWT_ISSUER = "auth_service"
JWT_AUDIENCE = "ai_platform"
JWT_ACCESS_TOKEN_SECONDS = 900  # 15 minutes

TOKEN_VALIDATION_CACHE_TTL = 0  # No caching in dev

RECOMMENDATIONS:
- Use HS256 for simpler setup
- Short token TTL for testing
- No caching to see live changes
- Detailed logging enabled


PRODUCTION
──────────

JWT_ALGORITHM = "RS256"
JWT_SECRET_KEY = "<RSA-PUBLIC-KEY-PEM>"  # From Secrets Manager
JWT_ISSUER = "auth_service"
JWT_AUDIENCE = "ai_platform"
JWT_ACCESS_TOKEN_SECONDS = 900  # 15 minutes
JWT_REFRESH_TOKEN_DAYS = 30

TOKEN_VALIDATION_CACHE_TTL = 60  # 1 minute
RATE_LIMIT_AUTH_ENDPOINTS = "5/minute"  # Per IP

RECOMMENDATIONS:
- Use RS256 for asymmetric signing
- Store public key in service config
- Private key ONLY in auth-service vault
- Enable token validation caching
- Short cache TTL for revocation responsiveness
- Rate limiting on auth endpoints
- Structured logging to ELK
- Alert on auth failure spikes
"""

# =============================================================================
# TROUBLESHOOTING
# =============================================================================

"""
PROBLEM: "AuthorizationError: Missing token"
CAUSE: Route requires @require_authenticated but no token provided
FIX: 
  1. Is client sending Authorization header?
  2. Is format "Bearer <token>"?
  3. Does route need authentication? (@require_authenticated)

PROBLEM: "Invalid token signature"
CAUSE: Token signed with different key than configured
FIX:
  1. Check JWT_SECRET_KEY matches auth-service
  2. If RS256, verify public key is correct
  3. Check JWT_ISSUER and JWT_AUDIENCE match token claims

PROBLEM: "Token has expired"
CAUSE: Access token TTL exceeded
FIX:
  1. Use refresh token to get new access token
  2. Check server time is synchronized (NTP)
  3. Increase JWT_ACCESS_TOKEN_SECONDS if needed (not recommended)

PROBLEM: "User lacks required role"
CAUSE: User doesn't have required role in JWT
FIX:
  1. Check user's roles in auth-service
  2. Verify JWT includes roles claim
  3. Check token was reissued after role change

PROBLEM: "Not authorized to access this resource"
CAUSE: Resource ownership check failed
FIX:
  1. Verify user_id in auth context
  2. Verify resource owner in database
  3. Check owner_id_getter function

PROBLEM: Middleware runs but route handler sees None auth_context
CAUSE: Middleware didn't run or token validation failed silently
FIX:
  1. Check before_request hook registered
  2. Check error handler is configured
  3. Add logging to middleware

PROBLEM: JWT validation is slow
CAUSE: Token validation cached insufficiently or crypto slow
FIX:
  1. Enable token validation caching
  2. Increase cache TTL if revocation not critical
  3. Use HS256 if possible (faster than RS256)
  4. Parallelize token validation if many requests
"""

# =============================================================================
# MIGRATION PATH: FROM NO AUTH TO RBAC
# =============================================================================

"""
PHASE 1: Add JWT validation without enforcement (1-2 days)
  - Add JwtHandler and middleware
  - Extract and inject auth_context
  - Add logging
  - No route protection yet (all still public)
  - GOAL: Collect token information, establish baseline

PHASE 2: Protect critical endpoints (2-3 days)
  - Add @require_authenticated to sensitive routes
  - Add @require_role checks for admin endpoints
  - Start rejecting unauthenticated requests to protected endpoints
  - GOAL: Critical functionality secured

PHASE 3: Protect all endpoints (3-5 days)
  - Categorize all routes (public, user, admin)
  - Add @require_authenticated to user endpoints
  - Add @require_role to admin endpoints
  - Mark truly public routes with @optional_authentication or no decorator
  - GOAL: Full RBAC coverage

PHASE 4: Fine-grained controls (ongoing)
  - Add resource ownership checks
  - Add custom policies (quotas, department-based, etc.)
  - Add audit logging
  - GOAL: Advanced authorization scenarios

PHASE 5: Monitoring & optimization (ongoing)
  - Monitor auth failures
  - Cache token validation
  - Set up alerts
  - GOAL: Production-ready
"""

# =============================================================================
# DEPLOYMENT CHECKLIST
# =============================================================================

"""
PRE-DEPLOYMENT CHECKLIST:

Code:
  □ All sensitive routes protected with @require_authenticated or @require_role
  □ No hardcoded JWT_SECRET_KEY in code
  □ Error handlers registered for all authorization errors
  □ Logging configured for authorization events
  □ Tests cover auth success and failure cases

Configuration:
  □ JWT_ALGORITHM set to "RS256" (not HS256)
  □ JWT_SECRET_KEY contains RSA public key (PEM format)
  □ JWT_ISSUER matches auth-service
  □ JWT_AUDIENCE set appropriately
  □ Rate limiting configured on auth endpoints

Operations:
  □ Private key stored in secure vault
  □ Public key distributed to all services
  □ Monitoring alerts configured
  □ On-call runbooks created
  □ Incident response procedures documented

Documentation:
  □ API docs updated with auth requirements
  □ Troubleshooting guide created
  □ Security contact information shared
  □ Team trained on RBAC concepts

Testing:
  □ Load test with authorization checks
  □ Test token expiration handling
  □ Test role changes (immediate reflection?)
  □ Test service-to-service auth
  □ Manual integration testing with real tokens
"""

if __name__ == "__main__":
    print("See IMPLEMENTATION_EXAMPLES.py, BEST_PRACTICES.md, ARCHITECTURE.md")
