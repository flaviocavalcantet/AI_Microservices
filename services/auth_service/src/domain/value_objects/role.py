"""Role value object for future role-based authorization."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    """Represents an authorization role name without policy logic."""

    name: str

    def __post_init__(self):
        if not self.name or not self.name.strip():
            raise ValueError("Role name must not be blank")
