# Authentication & Authorization Architecture

Production-grade OAuth2 + JWT authentication for the AI microservices platform.

## Overview

The platform uses a **hub-and-spoke trust model**:

- **auth-service** is the single identity authority: OAuth with external providers, internal JWT issuance, refresh token lifecycle.
- **All other services** validate JWTs locally (shared secret or JWKS) — no per-request round-trip to auth-service.

auth-service is only in the hot path during **login** and **token refresh**.

## Token Flows

### 1. OAuth login (authorization code + PKCE)

```
Browser → GET /api/v1/auth/oauth/{provider}/authorize
       ← authorization_url, state, code_verifier, code_challenge

Browser → OAuth provider consent screen
       ← redirect with ?code=&state=

Client  → GET|POST /api/v1/auth/oauth/{provider}/callback
       ← { access_token, refresh_token, expires_in }
```

auth-service never forwards the provider token to other services. It exchanges the code, resolves the user, and issues **platform JWTs** with roles and `session_id`.

### 2. Authenticated API request

```
Client → api-service (Authorization: Bearer <access_jwt>)
api-service → validates signature + claims locally
```

### 3. Refresh (rotation)

```
Client → POST /api/v1/auth/token/refresh { refresh_token }
       ← new access_token + new refresh_token
```

Each refresh **invalidates** the previous refresh token. Reuse of a revoked token revokes the entire **session family** (theft detection).

### 4. Logout

```
Client → POST /api/v1/auth/token/revoke { refresh_token }
```

Revokes all tokens in the session family.

## Trust Boundaries

| Zone | Trust level | Responsibility |
|------|-------------|----------------|
| External (browser, OAuth providers) | Untrusted | Validate all input at auth-service boundary |
| auth-service | Trusted issuer | Sign JWTs, manage refresh tokens |
| Internal services | Trust verified JWT claims only | Never trust raw headers without signature verification |

## JWT Claims Structure

```json
{
  "iss": "auth_service",
  "aud": "ai_platform",
  "sub": "user-uuid",
  "iat": 1716000000,
  "exp": 1716003600,
  "jti": "unique-token-id",
  "roles": ["user", "admin"],
  "email": "user@example.com",
  "provider": "github",
  "session_id": "session-uuid",
  "display_name": "Jane Doe",
  "avatar_url": "https://..."
}
```

| Claim | Purpose |
|-------|---------|
| `sub` | Platform user ID |
| `jti` | Unique token ID (future revocation lists) |
| `roles` | RBAC authorization |
| `session_id` | Ties access token to refresh token family |
| `provider` | Originating OAuth provider |

**Access token TTL:** 15 minutes default (`JWT_ACCESS_TOKEN_SECONDS=900`).  
**Refresh tokens:** Opaque 64-byte URL-safe strings; only SHA-256 hashes stored server-side. TTL: 30 days default.

## Signing Strategy

| Environment | Algorithm | Notes |
|-------------|-----------|-------|
| Development | HS256 | Shared `JWT_SECRET_KEY` — simple local validation |
| Production (recommended) | RS256 + JWKS | auth-service holds private key; services verify with public key only |

Config already exposes `JWT_ALGORITHM` for migration without code changes.

## OAuth Provider Integration

### Abstraction (`IOAuthProvider`)

| Method | Purpose |
|--------|---------|
| `build_authorization_url(state, code_challenge)` | Redirect to provider |
| `exchange_code(code, state, code_verifier)` | Code → userinfo dict |
| `get_userinfo(access_token)` | Profile fetch |

### GitHub (implemented)

- Library: `requests` (already in platform dependencies)
- PKCE: S256 (`code_challenge_method=S256`)
- Scopes: `read:user user:email`

### Environment variables

```bash
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GITHUB_REDIRECT_URI=http://localhost:5000/api/v1/auth/oauth/github/callback
GITHUB_OAUTH_SCOPES=read:user user:email
```

### Adding a provider

1. Implement `IOAuthProvider` in `infrastructure/oauth/`
2. Register in `OAuthProviderRegistry` inside `presentation/app.py`
3. No changes to use cases required

## Clean Architecture Layout

```
auth_service/src/
├── domain/           # User, RefreshToken, TokenClaims, events, exceptions
├── application/      # Use cases, DTOs, ports (interfaces)
├── infrastructure/   # JWT, OAuth, in-memory repos, event publisher
└── presentation/     # Flask routes, middleware
```

**Dependency rule:** presentation → application → domain. Infrastructure implements application ports.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/login` | Start OAuth (`provider`) or complete (`code`, `state`, `code_verifier`) |
| POST | `/api/v1/auth/refresh` | Rotate refresh token |
| GET | `/api/v1/auth/oauth/github` | Start GitHub OAuth (`?format=json` or redirect) |
| GET | `/api/v1/auth/oauth/github/callback` | GitHub redirect callback — issues tokens |
| POST | `/api/v1/auth/token/verify` | Validate access token (inter-service) |
| POST | `/api/v1/auth/token/revoke` | Logout — revoke session |

All responses use a standard envelope with `status`, `code`, `data`/`error`, `timestamp`, and `correlation_id`.

## Security Best Practices

1. **PKCE** — mandatory for authorization code flow (implemented)
2. **State parameter** — CSRF protection; one-time in-memory store (replace with Redis in production)
3. **Refresh token rotation** — limits blast radius of stolen refresh tokens
4. **Token family invalidation** — revoked token reuse triggers full session revoke
5. **Short access token TTL** — 15–60 minutes
6. **Never log tokens** — refresh tokens returned only at creation
7. **HTTPS only** in production for OAuth callbacks
8. **Production JWT secret** — minimum 32 characters (enforced in `ProductionConfig`)

## Persistence Status

Database persistence is **not implemented** yet. Development uses:

- `InMemoryUserRepository`
- `InMemoryRefreshTokenRepository`
- `InMemoryOAuthStateStore`
- `NoOpEventPublisher`

Replace with MongoDB repositories and RabbitMQ publisher when ready.

## Microservice JWT Validation

Other services should:

1. Verify `iss`, `aud`, `exp`, signature
2. Extract `sub` as `user_id`, `roles` for authorization
3. Use `RoleBasedAuthorizationPolicy` pattern or `@require_role` decorator

See `services/auth_service/templates/jwt_auth_middleware.py` for a copy-paste template.

## Future: SSO Compatibility

The internal JWT format is provider-agnostic. Adding SAML/OIDC enterprise IdPs means:

1. New `IOAuthProvider`-like adapter for the IdP
2. Same `OAuthLoginUseCase` path after userinfo normalization
3. Optional `tenant_id` claim for multi-tenant SSO

## Related Documentation

- [IDENTITY_PROPAGATION.md](./IDENTITY_PROPAGATION.md) — JWT, correlation IDs, SPIFFE, tracing across services
- [ARCHITECTURE.md](./ARCHITECTURE.md) — platform overview
- [CLEAN_ARCHITECTURE.md](./CLEAN_ARCHITECTURE.md) — layer responsibilities
- [ENVIRONMENT_CONFIGURATION.md](./ENVIRONMENT_CONFIGURATION.md) — secrets management
