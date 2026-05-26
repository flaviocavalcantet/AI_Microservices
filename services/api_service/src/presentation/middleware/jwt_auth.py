"""jwt_auth.py has been removed.

JWT validation for api-service now lives in ``jwt_middleware.py``, which
delegates to ``shared_auth.HMACJWTHandler`` / ``AuthorizationMiddleware``.

If you have a stale import of ``register_jwt_auth`` or ``get_require_auth``
from this module, update it to:

    from services.api_service.src.presentation.middleware.jwt_middleware import (
        register_jwt_auth,
        get_require_auth,
    )

Or, since both are already re-exported through the middleware package
``__init__.py``, the canonical call is:

    from services.api_service.src.presentation.middleware import register_auth_middleware
"""

raise ImportError(
    "jwt_auth.py has been removed. "
    "Import from jwt_middleware or the middleware package instead."
)
