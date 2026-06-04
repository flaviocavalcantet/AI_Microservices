# shared_auth — Architecture

Role-based authorization (RBAC) for the AI Microservices platform. Provides JWT validation, identity propagation, and composable authorization policies as a shared module consumed by all services.

## Module structure

```
shared_auth/
├── models.py       — Role, AuthContext, Permission, ServicePrincipal
├── errors.py       — Exception hierarchy (AuthorizationError, InsufficientPermissionsError, …)
├── jwt_handler.py  — HMACJWTHandler (HS256), RSAJWTHandler (RS256), factory
├── policies.py     — RoleBasedAuthorizationPolicy, ResourceOwnershipPolicy, CompositeAuthorizationPolicy, …
├── middleware.py   — AuthorizationMiddleware + route decorators
└── __init__.py     — Public API exports
```

## Layers

```
┌─────────────────────────────────────────────────────────┐
│  DECORATOR LAYER  — protect Flask routes                 │
│  @require_authenticated  @require_role                   │
│  @require_resource_ownership  @require_policy            │
│  @optional_authentication                                │
├─────────────────────────────────────────────────────────┤
│  MIDDLEWARE LAYER  — AuthorizationMiddleware             │
│  Runs as before_request hook; sets g.auth_context        │
├─────────────────────────────────────────────────────────┤
│  POLICY LAYER  — authorization decisions                 │
│  RoleBasedAuthorizationPolicy                            │
│  ResourceOwnershipPolicy                                 │
│  CompositeAuthorizationPolicy  (AND / OR)                │
│  TimeBasedPolicy  ·  PermissionBasedPolicy               │
├─────────────────────────────────────────────────────────┤
│  DOMAIN LAYER  — models.py                               │
│  Role (ADMIN | USER | WORKER)                            │
│  AuthContext  ·  Permission  ·  ServicePrincipal         │
├─────────────────────────────────────────────────────────┤
│  JWT LAYER  — jwt_handler.py                             │
│  HMACJWTHandler (HS256 — development)                    │
│  RSAJWTHandler  (RS256 — production)                     │
└─────────────────────────────────────────────────────────┘
```

## Request flow

```
Client  →  Authorization: Bearer <token>
              │
              ▼
        before_request hook
        AuthorizationMiddleware.validate_token()
              │
              ├─ extract_bearer_token()       → raw token string
              ├─ jwt_handler.validate_token() → decoded claims
              └─ AuthContext(user_id, roles, session_id, …)
                            │
                            ▼
                    g.auth_context = auth_context
                            │
                            ▼
              Route decorator (@require_role, …)
                            │
                            ▼
              Route handler  →  Response
```

**Error path:** any validation failure raises a typed exception (`InvalidTokenError`, `TokenExpiredError`, etc.) which Flask's error handler maps to 401 or 403.

## Component design

### `JWTHandler`

Abstract base; subclasses implement `validate_signature()`. Returns an `AuthContext` — never raw claims.

| Method | Description |
|--------|-------------|
| `validate_token(token)` | Validate and return `AuthContext`. Raises `MissingTokenError`, `InvalidTokenError`, `TokenExpiredError`. |
| `extract_bearer_token(header)` | Strip `Bearer ` prefix; raises if missing or malformed. |
| `validate_signature(token)` | Abstract — implemented by `HMACJWTHandler` / `RSAJWTHandler`. |

### `AuthContext`

Dataclass holding the authenticated identity for the lifetime of a request.

| Method | Returns |
|--------|---------|
| `has_role(role)` | `bool` |
| `has_any_role(roles)` | `bool` |
| `is_admin()` | `bool` |
| `is_worker()` | `bool` |
| `is_expired` | `bool` (property) |

### `AuthorizationPolicy`

Strategy pattern. Implement `evaluate(auth_context, **kwargs) -> bool` or use `assert_authorized()` which raises `InsufficientPermissionsError` on failure. Policies compose via `CompositeAuthorizationPolicy`.

### `AuthorizationMiddleware`

Registered via `app.before_request(middleware.validate_token)`. Sets `g.auth_context` to an `AuthContext` on success, or `None` for unauthenticated requests to public routes.

## Authorization decision matrix

| Action | Admin | User | Worker | Notes |
|--------|-------|------|--------|-------|
| Create job | ✓ all | ✓ own | ✗ | |
| Read job | ✓ all | ✓ own | ✗ | |
| Update job | ✓ all | ✓ own | ✗ | |
| Delete job | ✓ all | ✗ | ✗ | Admin only |
| Create task | ✓ | ✗ | ✓ | Service-to-service |
| List users | ✓ all | self only | ✗ | |
| Delete user | ✓ all | ✗ | ✗ | Admin only |

```python
# Create job
@require_role([Role.ADMIN, Role.USER])
def create_job(): ...

# Read job — ownership enforced in handler
@require_authenticated
def get_job(job_id):
    auth = assert_authenticated()
    job = get_job_by_id(job_id)
    if not auth.is_admin() and job.owner_id != auth.user_id:
        raise InsufficientPermissionsError()

# Delete job
@require_role(Role.ADMIN)
def delete_job(job_id): ...

# Service-to-service
@require_role(Role.WORKER)
def create_task(): ...
```

## Error hierarchy

```
AuthorizationError                    → HTTP 401
├── MissingTokenError
├── InvalidTokenError
└── TokenExpiredError

InsufficientPermissionsError          → HTTP 403
├── ResourceOwnershipError
└── PolicyEvaluationError
```

Register a single handler to cover both cases:

```python
@app.errorhandler(AuthorizationError)
def handle_auth_error(error):
    return {"error": error.code, "message": error.message}, error.status_code
```

## Extensibility

- **Custom JWT algorithm** — subclass `JWTHandler`, implement `validate_signature()`
- **Custom roles** — extend the `Role` enum
- **Custom policies** — subclass `AuthorizationPolicy`, implement `evaluate()`
- **Composed policies** — wrap multiple policies in `CompositeAuthorizationPolicy`

```python
class QuotaPolicy(AuthorizationPolicy):
    def __init__(self, max_per_user: int = 100):
        self.max = max_per_user

    def evaluate(self, auth_context: AuthContext, **kwargs) -> bool:
        if auth_context.is_admin():
            return True
        return get_user_resource_count(auth_context.user_id) < self.max

@app.route('/resources', methods=['POST'])
@require_policy(QuotaPolicy(max_per_user=100))
def create_resource(): ...
```

## Security principles

- **Default deny** — endpoints must explicitly grant access
- **Least privilege** — different permissions per action, not blanket role access
- **No trust without signature** — always validate JWT signature, issuer, audience, and expiry
- **Token rotation** — short-lived access tokens (15 min), refresh tokens (30 days)
- **Tokens in headers only** — never in URLs or response bodies
- **Audit logging** — all authorization decisions logged with `user_id`, `endpoint`, `method`, and outcome
