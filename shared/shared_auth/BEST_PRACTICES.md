"""Role-Based Authorization (RBAC) - Best Practices Guide

This guide provides best practices for implementing and maintaining
production-grade RBAC in Flask microservices.

Topics:
1. Architecture principles
2. Token management
3. Decorator composition
4. Error handling
5. Testing strategies
6. Security considerations
7. Extensibility patterns
8. Performance optimization
9. Common pitfalls
"""

# =============================================================================
# 1. ARCHITECTURE PRINCIPLES
# =============================================================================

"""
PRINCIPLE 1: Separation of Concerns
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Keep authorization logic separate from business logic:

    ✓ Good: Authorization checked at route boundary
    
    @app.route('/jobs/<job_id>')
    @require_authenticated
    @require_resource_ownership('job_id')
    def update_job(job_id):
        # Only business logic here
        return update_job_use_case(job_id, request.data)
    
    ✗ Bad: Authorization logic mixed with business logic
    
    def update_job_use_case(job_id, data):
        auth = g.auth_context
        job = get_job(job_id)
        
        # Authorization check buried in use case
        if auth.user_id != job.owner_id and not auth.is_admin():
            raise InsufficientPermissionsError()
        
        # ... business logic

WHY: Clearer intent, easier to test, centralized auth policy.


PRINCIPLE 2: Default-Deny Security
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Always deny by default, grant explicitly:

    ✓ Good: Explicit role requirement
    
    @app.route('/admin/users')
    @require_role(Role.ADMIN)
    def list_all_users():
        ...
    
    ✗ Bad: Everything allowed unless explicitly denied
    
    @app.route('/admin/users')
    def list_all_users():
        if g.auth_context and g.auth_context.is_admin():
            ...

WHY: Prevents accidental exposure of sensitive endpoints.


PRINCIPLE 3: Least Privilege
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Grant minimal permissions needed:

    ✓ Good: Users create but cannot delete
    
    @require_role([Role.USER, Role.ADMIN])  # Create only for users
    def create_job():
        ...
    
    @require_role(Role.ADMIN)  # Delete only for admins
    def delete_job():
        ...
    
    ✗ Bad: Same permission for all operations
    
    @require_role(Role.ADMIN)
    def create_job():
        ...
    
    @require_role(Role.ADMIN)
    def delete_job():
        ...  # Now regular admins are too powerful


PRINCIPLE 4: Audit & Logging
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Log all authorization decisions (especially failures):

    from shared.shared_logging import get_logger
    
    logger = get_logger(__name__)
    
    @require_role(Role.ADMIN)
    def delete_resource(resource_id):
        auth = assert_authenticated()
        logger.info(
            f"User {auth.user_id} deleted resource {resource_id}",
            extra={
                "resource_id": resource_id,
                "user_id": auth.user_id,
                "action": "delete",
            }
        )
        ...
    
    # Failed attempts:
    # Middleware logs: "Access denied: Insufficient permissions, "
    #                  "required_roles=['admin'], user_roles=['user']"

WHY: Audit trail, security monitoring, compliance requirements.
"""

# =============================================================================
# 2. TOKEN MANAGEMENT
# =============================================================================

"""
BEST PRACTICE 1: Token Validation Caching
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cache token validation to avoid repeated decoding:

    class CachingJWTHandler(JWTHandler):
        def __init__(self, jwt_handler, cache_ttl_seconds=60):
            self.jwt_handler = jwt_handler
            self.cache = {}  # Or Redis
            self.cache_ttl = cache_ttl_seconds
        
        def validate_token(self, token: str) -> AuthContext:
            # Check cache first
            cached = self.cache.get(token)
            if cached and not cached.is_expired:
                return cached
            
            # Validate (expensive)
            auth_context = self.jwt_handler.validate_token(token)
            
            # Cache result
            self.cache[token] = auth_context
            return auth_context

WHY: Token validation involves cryptographic operations;
caching reduces latency by 10-100x for high-traffic endpoints.

TRADEOFF: Token revocation list (TRL) not reflected immediately.
Mitigate with short cache TTL or invalidate on logout.


BEST PRACTICE 2: Token Expiration Strategy
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use short-lived access tokens + refresh tokens:

    # In auth-service config:
    JWT_ACCESS_TOKEN_SECONDS = 900       # 15 minutes
    JWT_REFRESH_TOKEN_DAYS = 30          # 30 days
    
    # Client flow:
    1. Login → get access_token (15 min) + refresh_token (30 days)
    2. Use access_token for API calls
    3. When access_token expires → POST /token/refresh
    4. Server validates refresh_token → issue new access_token
    5. If refresh_token compromised, rotate user session

WHY:
- Access token compromise = limited damage (15 min window)
- Refresh token compromise = can rotate user's session
- Doesn't require user to re-login every 15 minutes


BEST PRACTICE 3: Service-to-Service Tokens
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use long-lived service tokens with WORKER role:

    # In auth-service, issue for service:
    service_token = issue_service_token(
        service_id="api-service",
        expires_in=86400 * 365,  # 1 year
        roles=[Role.WORKER],
    )
    
    # Store in config or secure vault
    # API_SERVICE_JWT_TOKEN = "<long-lived-token>"
    
    # When calling ai-worker:
    headers = {
        "Authorization": f"Bearer {API_SERVICE_JWT_TOKEN}",
    }
    response = requests.post(
        "http://ai-worker:5000/api/v1/tasks",
        headers=headers,
        json={...}
    )

WHY:
- Services don't need to reauthenticate
- No user context to expire
- WORKER role separates service-to-service from user auth
"""

# =============================================================================
# 3. DECORATOR COMPOSITION
# =============================================================================

"""
BEST PRACTICE 1: Decorator Order Matters
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Put most restrictive decorators first (closest to function):

    ✓ Good: Fail fast on most restrictive
    
    @app.route('/admin/users')
    @require_role(Role.ADMIN)           # Fails here if not admin
    @require_resource_ownership(...)    # Only checked if admin
    def update_admin_settings():
        ...
    
    ✗ Bad: Unnecessary work before rejection
    
    @app.route('/admin/users')
    @require_resource_ownership(...)    # Expensive lookup even if not admin
    @require_role(Role.ADMIN)           # Fails here
    def update_admin_settings():
        ...

WHY: Performance - don't do expensive checks before fast role checks.


BEST PRACTICE 2: Reusable Decorator Composition
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Create decorator combinations for common patterns:

    # Define reusable combinations
    def admin_only(f):
        return require_role(Role.ADMIN)(f)
    
    def user_or_admin(f):
        return require_role([Role.ADMIN, Role.USER])(f)
    
    def owner_or_admin(f):
        return require_resource_ownership(allow_admin=True)(f)
    
    # Usage:
    @app.route('/jobs/<job_id>')
    @owner_or_admin
    def update_job(job_id):
        ...
    
    @app.route('/admin/jobs')
    @admin_only
    def list_all_jobs():
        ...

WHY: DRY principle, easier to read, consistent patterns.


BEST PRACTICE 3: Decorator Dependencies
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Some decorators depend on others:

    ✓ Good: Explicit dependency
    
    @app.route('/jobs/<job_id>')
    @require_authenticated           # Required by require_resource_ownership
    @require_resource_ownership()    # Needs authenticated user
    def update_job(job_id):
        ...
    
    ✗ Bad: Missing required decorator
    
    @app.route('/jobs/<job_id>')
    @require_resource_ownership()    # Will fail - no auth context!
    def update_job(job_id):
        ...

WHY: Prevents runtime errors and silent failures.
Decorators should fail explicitly if dependencies missing.
"""

# =============================================================================
# 4. ERROR HANDLING
# =============================================================================

"""
BEST PRACTICE 1: Distinct Error Responses
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Return correct HTTP status codes:

    401 Unauthorized:
    - No token provided
    - Token invalid/expired
    - User not authenticated
    
    403 Forbidden:
    - User authenticated but lacks permissions
    - Resource ownership check failed
    - Authorization policy failed
    
    400 Bad Request:
    - Malformed authorization header
    - Invalid token format

    ✓ Good: Correct status code
    
    def validate_token(self, token):
        if not token:
            raise MissingTokenError()  # 401
        
        if jwt.is_expired(token):
            raise TokenExpiredError()  # 401
    
    @require_role(Role.ADMIN)
    def admin_endpoint():
        # Raises InsufficientPermissionsError  # 403

WHY: Clients can handle errors appropriately.
401 → redirect to login. 403 → show "access denied".


BEST PRACTICE 2: Error Messages
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Clear, non-leaking error messages:

    ✓ Good: User-friendly, secure
    
    raise InsufficientPermissionsError(
        message="You don't have permission to access this resource"
    )
    
    Response:
    {
        "error": "FORBIDDEN",
        "message": "You don't have permission to access this resource"
    }
    
    ✗ Bad: Leaks implementation details
    
    raise InsufficientPermissionsError(
        message="User 'alice' (role: 'user') cannot access admin endpoint; "
                "required role: 'admin'; available roles: ['admin', 'user', 'worker']"
    )

WHY: Attacker learns system structure and can enumerate roles.
Don't expose internal role names unless necessary for debugging.


BEST PRACTICE 3: Logging vs. Response
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Log detailed info; return sanitized response:

    In middleware:
    
    logger.warning(
        f"Authorization failed: user_id={auth.user_id}, "
        f"required_roles={required_roles}, user_roles={user_roles}, "
        f"endpoint={request.path}"
    )
    
    To client:
    
    {
        "error": "FORBIDDEN",
        "message": "Insufficient permissions"
    }

WHY: Operations/security team has debug info; external clients don't.
"""

# =============================================================================
# 5. TESTING STRATEGIES
# =============================================================================

"""
BEST PRACTICE 1: Test Fixtures for Auth Contexts
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use fixtures for common auth contexts:

    @pytest.fixture
    def admin_context():
        return AuthContext(
            user_id="admin-123",
            roles=[Role.ADMIN],
            session_id="session-1",
            issued_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),
            jti="jti-1",
        )
    
    @pytest.fixture
    def user_context():
        return AuthContext(
            user_id="user-123",
            roles=[Role.USER],
            session_id="session-2",
            issued_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),
            jti="jti-2",
        )
    
    # Usage:
    def test_admin_can_delete(admin_context):
        with app.test_request_context():
            g.auth_context = admin_context
            response = delete_job('job-123')
            assert response.status_code == 204


BEST PRACTICE 2: Test All Authorization Paths
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test success and failure cases:

    def test_delete_job_by_admin(admin_context):
        # Success case
        assert delete_job('job-123') == 204
    
    def test_delete_job_by_user_fails(user_context):
        # Failure case - user
        with pytest.raises(InsufficientPermissionsError):
            delete_job('job-123')
    
    def test_delete_job_unauthenticated():
        # Failure case - no auth
        with app.test_request_context():
            g.auth_context = None
            with pytest.raises(MissingTokenError):
                delete_job('job-123')

WHY: Catch authorization regressions early.


BEST PRACTICE 3: Integration Tests
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test with real JWT tokens:

    def test_delete_job_with_jwt_token(admin_jwt_token):
        client = app.test_client()
        
        response = client.delete(
            '/api/v1/jobs/job-123',
            headers={'Authorization': f'Bearer {admin_jwt_token}'}
        )
        
        assert response.status_code == 204

WHY: Catches JWT generation/validation issues.
"""

# =============================================================================
# 6. SECURITY CONSIDERATIONS
# =============================================================================

"""
SECURITY 1: Never Trust Client Claims
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Always validate JWT signature before trusting claims:

    ✗ Bad: Trusting roles without validation
    
    def get_roles_from_header():
        return request.headers.get('X-Roles', '').split(',')
    
    ✓ Good: Validate JWT first
    
    auth_context = jwt_handler.validate_token(token)  # Validates signature
    roles = auth_context.roles  # Now we trust these


SECURITY 2: Protect Private Keys
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If using RS256:
- Private key only in auth-service
- Public key distributed to other services
- Never commit private key to version control
- Store in secure vault (HashiCorp Vault, AWS Secrets Manager)


SECURITY 3: Validate Token Claims
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Always check:
- Token not expired (exp claim)
- Correct issuer (iss claim)
- Correct audience (aud claim)
- Required claims present (sub, roles, session_id, jti)

JWTHandler does this automatically.


SECURITY 4: Rate Limiting on Auth Endpoints
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Protect auth endpoints from brute force:

    @auth_bp.route('/login', methods=['POST'])
    @limiter.limit("5 per minute")  # 5 login attempts per minute per IP
    def login():
        ...

WHY: Prevents dictionary attacks on user credentials.


SECURITY 5: Secure Token Storage (Client-Side)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For browser clients:
- Store access_token in memory (cleared on reload)
- Store refresh_token in httpOnly cookie (not accessible to JS)
- Can't be stolen via XSS

For native clients:
- Store in secure storage (Keychain, Keystore)
- Never in UserDefaults/SharedPreferences
"""

# =============================================================================
# 7. EXTENSIBILITY PATTERNS
# =============================================================================

"""
PATTERN 1: Custom Roles at Runtime
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Extend Role enum for custom roles:

    from enum import Enum
    
    class CustomRole(str, Enum):
        MODERATOR = "moderator"
        ANALYST = "analyst"
        ...
    
    # Use with type checking:
    allowed_roles = [Role.ADMIN, Role.USER, CustomRole.MODERATOR]


PATTERN 2: Custom Authorization Policies
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Implement custom policy for business logic:

    class DepartmentPolicy(AuthorizationPolicy):
        def __init__(self, required_department: str):
            self.required_department = required_department
        
        def evaluate(self, auth_context, **kwargs) -> bool:
            user_dept = get_user_department(auth_context.user_id)
            return user_dept == self.required_department
    
    # Usage:
    @app.route('/finance/reports')
    @require_policy(DepartmentPolicy("finance"))
    def list_finance_reports():
        ...


PATTERN 3: Dynamic Permission Mapping
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Load permissions from database:

    class DynamicPermissionPolicy(PermissionBasedPolicy):
        def __init__(self, db):
            super().__init__()
            self.db = db
            self._load_permissions()
        
        def _load_permissions(self):
            permissions = self.db.get_role_permissions()
            for role, perms in permissions.items():
                for perm in perms:
                    self.grant_permission(role, perm)
    
    # Allows updating permissions without code changes
"""

# =============================================================================
# 8. PERFORMANCE OPTIMIZATION
# =============================================================================

"""
OPTIMIZATION 1: Pre-compute Permissions
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cache role→permissions mapping:

    class CachedPermissionPolicy(PermissionBasedPolicy):
        def __init__(self, ttl_seconds=3600):
            super().__init__()
            self.ttl = ttl_seconds
            self.cache_time = 0
        
        def get_user_permissions(self, auth_context):
            # Return cached permissions
            return self.cache.get(auth_context.user_id, set())

WHY: Database lookups on every request are expensive.
Cache for 1 hour, invalidate on permission changes.


OPTIMIZATION 2: Fail Fast
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Order checks from cheapest to most expensive:

    @app.route('/resource/<resource_id>')
    @require_role(Role.ADMIN)           # O(1) - check role
    @require_resource_ownership(...)    # O(log n) - database lookup
    @require_policy(expensive_policy)   # O(n) - complex computation
    def update_resource(resource_id):
        ...

WHY: If role check fails, never hit expensive lookups.


OPTIMIZATION 3: Minimize JWT Validation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Validate once per request, reuse auth_context:

    # In middleware:
    @app.before_request
    def validate_jwt():
        # Expensive operation - done once
        g.auth_context = jwt_handler.validate_token(token)
    
    # In route handlers - reuse:
    @app.route('/jobs')
    def list_jobs():
        auth = g.auth_context  # Already validated
        ...

WHY: JWT validation includes cryptographic ops (expensive).
Do once per request, not once per decorator.
"""

# =============================================================================
# 9. COMMON PITFALLS
# =============================================================================

"""
PITFALL 1: Forgetting @require_authenticated
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✗ Bad: Assumes authentication but doesn't require it

    @app.route('/profile')
    def get_profile():
        auth = g.auth_context  # Will be None if no token!
        return {"user_id": auth.user_id}  # Crashes

✓ Good: Explicitly require authentication

    @app.route('/profile')
    @require_authenticated
    def get_profile():
        auth = assert_authenticated()
        return {"user_id": auth.user_id}  # Safe


PITFALL 2: Leaky Authorization Checks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✗ Bad: Authorization check after partial execution

    @app.route('/jobs', methods=['POST'])
    def create_job():
        data = request.get_json()
        job = Job.create(name=data['name'])  # DB write!
        
        # Authorization check AFTER creation
        if not can_user_create(g.auth_context, job):
            delete_job(job.id)  # Cleanup
            raise InsufficientPermissionsError()

✓ Good: Authorization check before action

    @app.route('/jobs', methods=['POST'])
    @require_role([Role.ADMIN, Role.USER])
    def create_job():
        data = request.get_json()
        job = Job.create(name=data['name'])  # Safe


PITFALL 3: Not Validating All Fields
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✗ Bad: Trust some claims without validation

    def validate_token(token):
        payload = jwt.decode(token, SECRET)  # Validates signature
        
        # But didn't check these!
        if payload['roles'] is None:  # Could crash
            ...
        if 'sub' not in payload:  # Required claim missing!
            ...

✓ Good: Validate all claims

    def validate_token(token):
        payload = jwt.decode(token, SECRET)
        auth_context = AuthContext.from_claims(payload)
        # AuthContext.__post_init__ validates all fields


PITFALL 4: Role Hierarchy Confusion
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✗ Bad: Assuming role hierarchy

    if auth.roles == [Role.ADMIN]:
        # Can only be admin, not admin + user
        ...

✓ Good: Check roles independently

    if auth.is_admin():
        # Can be any combination including admin
        ...


PITFALL 5: Exposing Internal State
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✗ Bad: Response leaks user info

    def get_profile(user_id):
        user = get_user(user_id)
        if not user:
            return {"error": "User not found", "user_id": user_id}, 404
        
        # Returns 404 for non-existent, 403 for no permission
        # Attacker can enumerate user IDs!

✓ Good: Same response for missing/forbidden

    def get_profile(user_id):
        user = get_user(user_id)
        if not user or user.id != auth_context.user_id:
            return {"error": "Not found"}, 404
        
        # Return 404 for both missing and forbidden
"""

# =============================================================================
# SUMMARY: RBAC Implementation Checklist
# =============================================================================

"""
Before production deployment, verify:

□ JWT validation middleware registered globally
□ All protected routes have @require_authenticated or @require_role
□ Default-deny security: unauthenticated requests rejected
□ Error handlers for AuthorizationError, InsufficientPermissionsError
□ Distinct HTTP status codes (401 vs 403)
□ Authorization decisions logged with user_id, action, result
□ No sensitive info in error responses
□ Token expiration checked in middleware
□ Resource ownership verified for user-specific resources
□ Service-to-service calls use WORKER role tokens
□ Decorators ordered from most to least restrictive
□ Tests cover success and failure authorization paths
□ Admin overrides (if any) documented and limited
□ Performance tested with many concurrent requests
□ Token validation caching (if high throughput)
□ Refresh token rotation implemented
□ Rate limiting on authentication endpoints

Questions answered:
✓ Who can create? (roles)
✓ Who can read? (ownership + roles)
✓ Who can update? (ownership + admin)
✓ Who can delete? (admin only)
✓ Service-to-service? (WORKER role)
✓ Resource ownership? (explicit checks)
✓ Role hierarchy? (none - independent)
✓ Future extensions? (custom policies)
"""

if __name__ == "__main__":
    print("See IMPLEMENTATION_EXAMPLES.py for concrete code examples")
    print("See models.py, policies.py, middleware.py for implementation")
