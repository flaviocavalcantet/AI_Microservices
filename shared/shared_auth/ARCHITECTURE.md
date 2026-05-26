"""Role-Based Authorization Architecture

Comprehensive architecture documentation for the RBAC system.

Contents:
1. System Architecture
2. Component Design
3. Request Flow
4. Authorization Decision Model
5. Error Handling
6. Extensibility
7. Security Model
"""

# =============================================================================
# 1. SYSTEM ARCHITECTURE
# =============================================================================

"""
╔════════════════════════════════════════════════════════════════════════════╗
║                    RBAC System Architecture                                 ║
╚════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────┐
│ SHARED_AUTH MODULE (shared/shared_auth/)                                    │
│                                                                              │
│ ┌──────────────────────────────────────────────────────────────────────┐   │
│ │ JWT LAYER                                                             │   │
│ │                                                                       │   │
│ │  JWTHandler (abstract)                                              │   │
│ │   ├─ HMACJWTHandler (HS256 - development)                          │   │
│ │   └─ RSAJWTHandler (RS256 - production)                            │   │
│ │                                                                       │   │
│ │  Responsibilities:                                                   │   │
│ │  - Validate signature                                               │   │
│ │  - Extract claims from token                                        │   │
│ │  - Verify issuer and audience                                       │   │
│ │  - Check expiration                                                 │   │
│ └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│ ┌──────────────────────────────────────────────────────────────────────┐   │
│ │ DOMAIN LAYER                                                         │   │
│ │                                                                       │   │
│ │  Role (enum): [ADMIN, USER, WORKER]                                 │   │
│ │  Permission: {resource, action, owner_required}                     │   │
│ │  AuthContext: {user_id, roles, session_id, ...}                    │   │
│ │  ServicePrincipal: {service_id, roles, ...}                        │   │
│ │                                                                       │   │
│ │  Responsibilities:                                                   │   │
│ │  - Represent authentication/authorization concepts                  │   │
│ │  - Provide convenient methods (is_admin(), has_role(), etc.)       │   │
│ │  - Immutable data representation                                    │   │
│ └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│ ┌──────────────────────────────────────────────────────────────────────┐   │
│ │ POLICY LAYER                                                         │   │
│ │                                                                       │   │
│ │  AuthorizationPolicy (abstract)                                     │   │
│ │   ├─ RoleBasedAuthorizationPolicy                                   │   │
│ │   ├─ ResourceOwnershipPolicy                                        │   │
│ │   ├─ PermissionBasedPolicy                                          │   │
│ │   ├─ TimeBasedPolicy                                                │   │
│ │   └─ CompositeAuthorizationPolicy                                   │   │
│ │                                                                       │   │
│ │  Responsibilities:                                                   │   │
│ │  - Encapsulate authorization logic                                  │   │
│ │  - Make authorization decisions                                     │   │
│ │  - Support composition of multiple policies                         │   │
│ │  - Be testable independently                                        │   │
│ └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│ ┌──────────────────────────────────────────────────────────────────────┐   │
│ │ MIDDLEWARE LAYER                                                     │   │
│ │                                                                       │   │
│ │  AuthorizationMiddleware                                             │   │
│ │   └─ validate_token(): Runs before each request                     │   │
│ │       Sets g.auth_context                                           │   │
│ │                                                                       │   │
│ │  Responsibilities:                                                   │   │
│ │  - Extract token from Authorization header                          │   │
│ │  - Validate JWT signature                                           │   │
│ │  - Inject auth_context into request                                │   │
│ │  - Handle validation errors                                         │   │
│ └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│ ┌──────────────────────────────────────────────────────────────────────┐   │
│ │ DECORATOR LAYER                                                      │   │
│ │                                                                       │   │
│ │  @require_authenticated                                              │   │
│ │  @require_role(roles)                                                │   │
│ │  @require_all_roles(roles)                                           │   │
│ │  @require_permission(checker)                                        │   │
│ │  @require_resource_ownership(...)                                    │   │
│ │  @require_policy(policy)                                             │   │
│ │  @optional_authentication                                            │   │
│ │                                                                       │   │
│ │  Responsibilities:                                                   │   │
│ │  - Protect Flask routes                                             │   │
│ │  - Check authorization before handler executes                      │   │
│ │  - Raise InsufficientPermissionsError if denied                     │   │
│ │  - Composable and chainable                                         │   │
│ └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│ ┌──────────────────────────────────────────────────────────────────────┐   │
│ │ ERROR LAYER                                                          │   │
│ │                                                                       │   │
│ │  AuthorizationError (base) → HTTP 401                               │   │
│ │   ├─ MissingTokenError                                              │   │
│ │   ├─ InvalidTokenError                                              │   │
│ │   └─ TokenExpiredError                                              │   │
│ │                                                                       │   │
│ │  InsufficientPermissionsError (extends) → HTTP 403                  │   │
│ │   ├─ ResourceOwnershipError                                         │   │
│ │   └─ PolicyEvaluationError                                          │   │
│ │                                                                       │   │
│ │  Responsibilities:                                                   │   │
│ │  - Distinguish auth failures (401) from permission failures (403)   │   │
│ │  - Provide debugging info in logs                                   │   │
│ │  - Return user-friendly messages in responses                       │   │
│ └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
"""

# =============================================================================
# 2. COMPONENT DESIGN
# =============================================================================

"""
COMPONENT: JWTHandler

Purpose: Validate JWT tokens and extract claims

Design Decisions:
- Abstract base class allows multiple implementations (HS256, RS256, custom)
- Single responsibility: Validate and extract, nothing else
- Returns AuthContext (domain object), not raw claims
- Raises specific exceptions for different failure modes

Public Methods:
  validate_token(token: str) -> AuthContext
    Validates JWT and returns auth context
    Raises: MissingTokenError, InvalidTokenError, TokenExpiredError
  
  extract_bearer_token(auth_header: str) -> str
    Extracts token from Authorization header
    Raises: MissingTokenError, InvalidTokenError
  
  validate_signature(token: str) -> Dict[str, Any]  [abstract]
    Validates signature, implemented by subclasses


COMPONENT: AuthContext

Purpose: Represent authenticated user in request

Design Decisions:
- Immutable (dataclass with frozen=False but shouldn't be modified)
- Contains all info needed for authorization checks
- Provides convenience methods (is_admin(), has_role(), etc.)
- Includes extra_claims for extensibility

Public Methods:
  has_role(role: Role) -> bool
  has_any_role(roles: List[Role]) -> bool
  has_all_roles(roles: List[Role]) -> bool
  is_admin() -> bool
  is_worker() -> bool
  is_expired -> bool


COMPONENT: AuthorizationPolicy

Purpose: Encapsulate authorization logic

Design Decisions:
- Strategy pattern: Different policy implementations for different checks
- Testable: Can test policy.evaluate() independently
- Composable: CompositeAuthorizationPolicy combines policies
- Extensible: Easy to add new policy types

Public Methods:
  evaluate(auth_context: AuthContext, **kwargs) -> bool
    Returns True if authorized, False otherwise
  
  assert_authorized(auth_context: AuthContext, **kwargs) -> None
    Raises InsufficientPermissionsError if not authorized


COMPONENT: AuthorizationMiddleware

Purpose: Inject auth_context into Flask request

Design Decisions:
- Runs once per request (before_request hook)
- Allows missing token (public routes don't have Authorization header)
- Sets g.auth_context (Flask request context variable)
- Raises exceptions for error handling middleware

Public Methods:
  validate_token() -> Optional[Dict]
    Called by app.before_request(middleware.validate_token)
  
  get_auth_context() -> Optional[AuthContext]
    Get current request's auth context
"""

# =============================================================================
# 3. REQUEST FLOW
# =============================================================================

"""
REQUEST FLOW: Authenticated API Call

┌─────────────┐
│   Client    │
└──────┬──────┘
       │ GET /api/v1/jobs
       │ Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
       │
       ▼
┌─────────────────────────────────────────┐
│  STEP 1: Flask Request                   │
│  request.headers['Authorization']        │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  STEP 2: Before Request Hook             │
│  app.before_request(                     │
│    auth_middleware.validate_token        │
│  )                                       │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  STEP 3: Extract Bearer Token            │
│  jwt_handler.extract_bearer_token(       │
│    "Bearer eyJ0eXAi..."                 │
│  )                                       │
│  → "eyJ0eXAi..."                        │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  STEP 4: Validate Signature              │
│  jwt.decode(token, secret, ...)          │
│  → Claims: {                             │
│    "sub": "user-123",                   │
│    "roles": ["user"],                   │
│    "exp": 1716003600,                   │
│    ...                                   │
│  }                                       │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  STEP 5: Validate Claims                 │
│  - Check issuer, audience                │
│  - Check expiration                      │
│  - Validate required claims              │
│  - Parse roles                           │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  STEP 6: Create AuthContext              │
│  AuthContext(                            │
│    user_id="user-123",                  │
│    roles=[Role.USER],                   │
│    session_id="session-456",            │
│    ...                                   │
│  )                                       │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  STEP 7: Inject into Request Context    │
│  g.auth_context = auth_context          │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  STEP 8: Route Handler Execution         │
│  @app.route('/api/v1/jobs')              │
│  @require_authenticated                  │
│  def list_jobs():                        │
│    auth = g.auth_context  # Already     │
│    # available from step 7               │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────┐
│  Response   │
└─────────────┘


ERROR FLOW: Invalid Token

┌─────────────┐
│   Client    │
└──────┬──────┘
       │ GET /api/v1/jobs
       │ Authorization: Bearer invalid.token...
       │
       ▼
┌─────────────────────────────────────────┐
│  Before Request Hook                     │
└──────┬──────────────────────────────────┘
       │
       ├─→ extract_bearer_token()
       │   ✓ → "invalid.token..."
       │
       ├─→ validate_signature()
       │   ✗ → jwt.InvalidSignatureError
       │
       ├─→ Catch and raise InvalidTokenError
       │
       ▼
┌─────────────────────────────────────────┐
│  Error Handler                           │
│  @app.errorhandler(InvalidTokenError)    │
│  def handle_invalid_token(error):        │
│    return {"error": "UNAUTHORIZED"}, 401 │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  HTTP 401 Response                       │
│  {                                       │
│    "error": "UNAUTHORIZED",              │
│    "message": "Invalid token signature"  │
│  }                                       │
└─────────────────────────────────────────┘
"""

# =============================================================================
# 4. AUTHORIZATION DECISION MODEL
# =============================================================================

"""
DECISION MATRIX: Who can perform what action?

┌──────────┬────────┬────────┬────────┬────────┬────────────┐
│ Action   │ Admin  │ User   │ Worker │ Owner  │ Notes      │
├──────────┼────────┼────────┼────────┼────────┼────────────┤
│ Create   │ ✓      │ ✓      │ ✗      │ N/A    │ Users can  │
│ Job      │ (all)  │ (own)  │        │        │ create own │
├──────────┼────────┼────────┼────────┼────────┼────────────┤
│ Read     │ ✓      │ ✓      │ ✗      │ ✓      │ Users see  │
│ Job      │ (all)  │ (own)  │        │ (own)  │ only owned │
├──────────┼────────┼────────┼────────┼────────┼────────────┤
│ Update   │ ✓      │ ✓      │ ✗      │ ✓      │ Same as    │
│ Job      │ (all)  │ (own)  │        │ (own)  │ read       │
├──────────┼────────┼────────┼────────┼────────┼────────────┤
│ Delete   │ ✓      │ ✗      │ ✗      │ ✗      │ Admins     │
│ Job      │ (all)  │        │        │        │ only       │
├──────────┼────────┼────────┼────────┼────────┼────────────┤
│ Create   │ ✓      │ N/A    │ ✓      │ N/A    │ Service-to-│
│ Task     │ (all)  │        │        │        │ service    │
├──────────┼────────┼────────┼────────┼────────┼────────────┤
│ List     │ ✓      │ ✓      │ ✗      │ N/A    │ Admins see │
│ All Users│ (all)  │ (self) │        │        │ everyone   │
├──────────┼────────┼────────┼────────┼────────┼────────────┤
│ Delete   │ ✓      │ ✗      │ ✗      │ ✗      │ Admins     │
│ User     │ (all)  │        │        │        │ only       │
└──────────┴────────┴────────┴────────┴────────┴────────────┘

Implementation Patterns:

Create Job:
  @require_role([Role.ADMIN, Role.USER])
  def create_job():
    ...

Read Job:
  @require_authenticated
  def get_job(job_id):
    auth = assert_authenticated()
    job = get_job_by_id(job_id)
    
    # Admin can see all, user sees own
    if not auth.is_admin() and job.owner_id != auth.user_id:
      raise InsufficientPermissionsError()

Update Job:
  @require_resource_ownership('job_id')
  def update_job(job_id):
    # Can be chained with @require_role
    ...

Delete Job:
  @require_role(Role.ADMIN)
  def delete_job(job_id):
    ...

Create Task (service-to-service):
  @require_role(Role.WORKER)
  def create_task():
    ...
"""

# =============================================================================
# 5. ERROR HANDLING
# =============================================================================

"""
ERROR HIERARCHY & HTTP MAPPING

AuthorizationError (abstract base)
├── HTTP 401 Unauthorized
│   ├─ MissingTokenError
│   ├─ InvalidTokenError
│   └─ TokenExpiredError
│
└── InsufficientPermissionsError (extends AuthorizationError)
    └── HTTP 403 Forbidden
        ├─ ResourceOwnershipError
        └─ PolicyEvaluationError

WHEN TO USE EACH:

401 Unauthorized:
- No Authorization header provided
- Token is malformed
- Token signature is invalid
- Token has expired
- Required claims are missing

401 Response:
{
  "error": "UNAUTHORIZED",
  "message": "Authentication token required",
  "code": "MISSING_TOKEN"
}

403 Forbidden:
- User is authenticated but lacks required role
- User is authenticated but is not resource owner
- User is authenticated but policy check failed

403 Response:
{
  "error": "FORBIDDEN",
  "message": "You don't have permission to perform this action",
  "code": "INSUFFICIENT_PERMISSIONS",
  "details": {
    "required_roles": ["admin"],
    "resource_id": "job-123"
  }
}

LOGGING:

Errors are logged with full context in middleware/decorators:

logger.warning(
  "Authorization failed",
  extra={
    "event": "authorization_failure",
    "error_type": "InsufficientPermissionsError",
    "user_id": "user-123",
    "required_roles": ["admin"],
    "user_roles": ["user"],
    "endpoint": "/api/v1/jobs/job-123",
    "method": "DELETE",
    "ip_address": "192.168.1.1",
  }
)
"""

# =============================================================================
# 6. EXTENSIBILITY
# =============================================================================

"""
EXTENSION POINTS:

1. Custom JWT Handlers
   - Implement JWTHandler abstract base
   - Support different signing algorithms
   - Example: WebAuthn, SAML, OAuth2

2. Custom Roles
   - Extend Role enum
   - Update policies to recognize new roles
   - Example: MODERATOR, ANALYST, MANAGER

3. Custom Policies
   - Extend AuthorizationPolicy abstract base
   - Implement domain-specific authorization
   - Example: DepartmentPolicy, QuotaPolicy

4. Custom Decorators
   - Compose existing decorators
   - Create domain-specific shortcuts
   - Example: @finance_admin, @content_moderator

5. Dynamic Role/Permission Loading
   - Load from database/cache
   - Update on-demand without code changes
   - Example: DynamicPermissionPolicy

6. External Authorization Services
   - Call external auth service for decisions
   - Example: OPA (Open Policy Agent)

7. Audit Trail
   - Log authorization decisions
   - Store in separate audit database
   - Enable compliance reporting

Example: Custom Policy
─────────────────────

from shared_auth import AuthorizationPolicy, AuthContext

class QuotaPolicy(AuthorizationPolicy):
    def __init__(self, max_resources_per_user=100):
        self.max = max_resources_per_user
    
    def evaluate(self, auth_context: AuthContext, **kwargs) -> bool:
        # Admin has unlimited quota
        if auth_context.is_admin():
            return True
        
        # Check user's resource count
        user_resources = get_user_resource_count(auth_context.user_id)
        return user_resources < self.max

# Usage:
quota_policy = QuotaPolicy(max_resources_per_user=100)

@app.route('/resources', methods=['POST'])
@require_policy(quota_policy)
def create_resource():
    ...
"""

# =============================================================================
# 7. SECURITY MODEL
# =============================================================================

"""
SECURITY PRINCIPLES:

1. Default Deny
   - All endpoints protected by default
   - Explicitly mark public endpoints
   - Fail if auth check is missing

2. Least Privilege
   - Grant minimal permissions needed
   - Different permissions for different actions
   - Regular audit of role assignments

3. Defense in Depth
   - Multiple layers of checks
   - Authorization at route and use case level
   - Don't rely on single check

4. No Token Trust Without Signature
   - Never trust JWT claims without validating signature
   - Always verify issuer and audience
   - Check token expiration

5. Secure Token Transport
   - Use HTTPS/TLS for all requests
   - Tokens in Authorization header, never in URL
   - Set secure cookies for refresh tokens

6. Token Rotation
   - Short-lived access tokens (15 minutes)
   - Refresh tokens (30 days)
   - Rotation on each refresh

7. Audit & Logging
   - Log all authorization decisions
   - Log failed attempts with context
   - Monitor for suspicious patterns

THREAT MODEL:

Threat: Token Stolen
├─ Mitigation 1: Short TTL (15 min)
├─ Mitigation 2: Token binding (IP, device)
└─ Mitigation 3: Monitoring for abnormal patterns

Threat: Role Escalation
├─ Mitigation 1: Strict role validation
├─ Mitigation 2: Default deny
└─ Mitigation 3: Audit trail

Threat: Resource Ownership Bypass
├─ Mitigation 1: Explicit ownership checks
├─ Mitigation 2: Never trust user_id from request
└─ Mitigation 3: Always validate from source of truth

Threat: Brute Force Auth
├─ Mitigation 1: Rate limiting on auth endpoints
├─ Mitigation 2: Account lockout
└─ Mitigation 3: Monitoring
"""

if __name__ == "__main__":
    print("See RBAC documentation for architecture details")
