"""Template: JWT authentication middleware for consuming microservices.

Copy into api-service (or any service) presentation/middleware/.
Validates Bearer tokens locally — no call to auth-service per request.
"""

from functools import wraps
from typing import Callable

import jwt
from flask import g, request

from services.auth_service.src.errors import ForbiddenError, UnauthorizedError


def create_jwt_auth_middleware(
    secret_key: str,
    algorithm: str,
    issuer: str,
    audience: str,
):
    """Factory returning a before_request hook and require_role decorator."""

    def load_claims():
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        token = auth[7:].strip()
        if not token:
            return None
        try:
            return jwt.decode(
                token,
                secret_key,
                algorithms=[algorithm],
                audience=audience,
                issuer=issuer,
            )
        except jwt.PyJWTError:
            return None

    def before_request():
        claims = load_claims()
        if claims:
            g.user_id = claims.get("sub")
            g.email = claims.get("email")
            g.roles = claims.get("roles", [])
            g.jwt_claims = claims

    def require_role(*required_roles: str):
        def decorator(fn: Callable):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                if not getattr(g, "user_id", None):
                    raise UnauthorizedError("Authentication required")
                held = set(getattr(g, "roles", []))
                if not any(r in held for r in required_roles):
                    raise ForbiddenError(
                        f"Requires one of roles: {', '.join(required_roles)}"
                    )
                return fn(*args, **kwargs)
            return wrapper
        return decorator

    return before_request, require_role
