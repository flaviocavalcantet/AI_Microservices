"""Role-based authorization adapter."""

from typing import List, Sequence

from ...application.ports.interfaces import IAuthorizationPolicy


class RoleBasedAuthorizationPolicy(IAuthorizationPolicy):
    """RBAC policy — checks role membership on JWT claims."""

    def has_role(self, user_roles: Sequence[str], required_role: str) -> bool:
        return required_role in set(user_roles)

    def has_any_role(self, user_roles: List[str], required_roles: List[str]) -> bool:
        held = set(user_roles)
        return any(role in held for role in required_roles)
