"""OAuth provider registry."""

from ...application.ports.interfaces import IOAuthProvider


class OAuthProviderRegistry:
    """Registry for OAuth provider adapters."""

    def __init__(self):
        self._providers: dict[str, IOAuthProvider] = {}

    def register(self, name: str, provider: IOAuthProvider) -> None:
        self._providers[name] = provider

    def get(self, name: str) -> IOAuthProvider:
        if name not in self._providers:
            raise ValueError(f"OAuth provider not registered: {name}")
        return self._providers[name]

    def names(self) -> list[str]:
        return sorted(self._providers)
