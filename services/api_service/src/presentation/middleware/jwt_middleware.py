"""JWT authentication middleware for api-service — backed by shared_auth.

Replaces the old local jwt_auth.py.  All JWT validation is now delegated to
``shared_auth.HMACJWTHandler`` / ``AuthorizationMiddleware`` so there is a
single, tested validation path across every service.

Public surface (unchanged from the previous implementation):
- ``register_jwt_auth(app, ...)``        — called by middleware __init__
- ``app.extensions["require_auth"]``     — decorator: enforce auth on a route
- ``app.extensions["require_role"]``     — decorator: enforce role(s) on a route
- ``g.user_id / g.email / g.roles /
   g.session_id / g.jwt_claims /
   g.bearer_token``                      — populated for every valid token
"""

from __future__ import annotations

import re
from functools import wraps
from typing import Callable, Iterable, Optional, Set

from flask import Flask, g, request

from services.api_service.src.errors import ForbiddenError, UnauthorizedError
from shared.shared_auth.jwt_handler import HMACJWTHandler
from shared.shared_auth.errors import (
    AuthorizationError,
    InvalidTokenError,
    InvalidClaimsError,
    MissingTokenError,
    TokenExpiredError,
)
from shared.shared_http.src.propagation import set_request_context


def _compile_exempt_patterns(paths: Iterable[str]) -> list[re.Pattern]:
    return [re.compile(p) for p in paths]


def _default_exempt_paths() -> tuple[str, ...]:
    return (
        r"^/health$",
        r"^/health/.*",
        r"^/apidocs/?",
        r"^/apispec\.json$",
        r"^/flasgger_static/.*",
    )


def register_jwt_auth(
    app: Flask,
    *,
    secret_key: str,
    algorithm: str,
    issuer: str,
    audience: str,
    enabled: bool = True,
    required: bool = False,
    exempt_paths: Optional[Iterable[str]] = None,
) -> Callable:
    """Register JWT parsing and optional enforcement using shared_auth.

    Args:
        app:          Flask application instance.
        secret_key:   HMAC secret — must match the auth-service issuer.
        algorithm:    Signing algorithm (e.g. "HS256").
        issuer:       Expected ``iss`` claim value.
        audience:     Expected ``aud`` claim value.
        enabled:      When False the entire before_request hook is skipped
                      (useful for unit tests that mock auth).
        required:     When True, requests without a token are rejected 401.
                      When False, missing token is allowed (optional auth).
        exempt_paths: Regex patterns for paths that skip JWT checks.
                      Defaults to health, apidocs, and flasgger routes.

    Returns:
        The ``require_auth`` decorator (also stored in app.extensions).
    """
    handler = HMACJWTHandler(
        secret_key=secret_key,
        issuer=issuer,
        audience=audience,
        algorithms=[algorithm],
    )

    exempt = _compile_exempt_patterns(exempt_paths or _default_exempt_paths())

    def _is_exempt() -> bool:
        return any(p.match(request.path) for p in exempt)

    def _extract_bearer() -> Optional[str]:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            raw = auth[7:].strip()
            return raw or None
        return None

    if enabled:

        @app.before_request
        def _jwt_before_request():
            if _is_exempt():
                return None

            raw_token = _extract_bearer()

            if not raw_token:
                if required:
                    raise UnauthorizedError("Bearer token required")
                return None

            # Delegate full validation to shared_auth — signature, expiry,
            # issuer/audience, required claims (exp, sub, jti, roles,
            # session_id), and token-type discrimination.
            try:
                auth_ctx = handler.validate_token(raw_token)
            except TokenExpiredError:
                raise UnauthorizedError("Token has expired")
            except (InvalidTokenError, InvalidClaimsError, AuthorizationError) as exc:
                raise UnauthorizedError(str(exc))

            # Reject refresh tokens presented as access tokens.
            # shared_auth stores the raw claims in the extra_claims dict for
            # any claim not in its known sets; token_type lives there.
            token_type = auth_ctx.extra_claims.get("token_type", "access")
            if token_type != "access":
                raise UnauthorizedError(f"Invalid token type: {token_type!r}")

            # Populate Flask g so that existing route helpers and the
            # propagation middleware can read identity without touching
            # auth_ctx directly.
            g.user_id = auth_ctx.user_id
            g.email = auth_ctx.email
            # auth_ctx.roles is List[Role] (enum); controllers expect strings.
            g.roles = [r.value for r in auth_ctx.roles]
            g.session_id = auth_ctx.session_id
            g.jwt_claims = {
                "sub": auth_ctx.user_id,
                "email": auth_ctx.email,
                "roles": g.roles,
                "session_id": auth_ctx.session_id,
                "jti": auth_ctx.jti,
                **auth_ctx.extra_claims,
            }
            g.bearer_token = raw_token
            g.auth_context = auth_ctx  # also expose typed context

            set_request_context(
                correlation_id=getattr(g, "correlation_id", None),
                request_id=getattr(g, "request_id", None),
                user_id=g.user_id,
                bearer_token=raw_token,
                traceparent=request.headers.get("traceparent"),
            )
            return None

    # ------------------------------------------------------------------
    # Decorators stored in app.extensions so routes can retrieve them
    # without a direct import of this module.
    # ------------------------------------------------------------------

    def require_auth(fn: Callable) -> Callable:
        """Route decorator: reject 401 if no authenticated user in context.

        When JWT_AUTH_ENABLED=False (test escape hatch) the middleware hook
        never runs, so g.user_id is never populated.  In that mode we skip
        the check entirely so validation-focused tests can reach their
        routes without supplying a token.
        """
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if enabled and not getattr(g, "user_id", None):
                raise UnauthorizedError("Authentication required")
            return fn(*args, **kwargs)
        return wrapper

    def require_role(*roles: str) -> Callable:
        """Route decorator: reject 403 unless user holds at least one role."""
        def decorator(fn: Callable) -> Callable:
            @wraps(fn)
            def wrapper(*args, **kwargs):
                if not getattr(g, "user_id", None):
                    raise UnauthorizedError("Authentication required")
                held: Set[str] = set(getattr(g, "roles", []) or [])
                if not any(role in held for role in roles):
                    raise ForbiddenError(
                        f"Requires one of roles: {', '.join(roles)}"
                    )
                return fn(*args, **kwargs)
            return wrapper
        return decorator

    app.extensions["require_auth"] = require_auth
    app.extensions["require_role"] = require_role
    return require_auth


def get_require_auth(app: Flask) -> Callable:
    """Retrieve the ``require_auth`` decorator registered with *app*."""
    return app.extensions.get("require_auth", lambda f: f)
