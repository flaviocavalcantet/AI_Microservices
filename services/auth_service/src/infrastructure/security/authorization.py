"""Role-based authorization adapter placeholder."""

from typing import Sequence

from ...application.ports.authorization_policy import AuthorizationPolicy


class RoleBasedAuthorizationPolicy(AuthorizationPolicy):
    """Simple RBAC-ready policy skeleton."""

    def has_role(self, user_roles: Sequence[str], required_role: str) -> bool:
        return required_role in set(user_roles)
