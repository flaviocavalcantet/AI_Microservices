"""OAuth provider registry placeholder."""

from ...application.ports.oauth_provider import OAuthProvider


class OAuthProviderRegistry:
    """Registry for future OAuth provider adapters."""

    def __init__(self):
        self._providers: dict[str, OAuthProvider] = {}

    def register(self, name: str, provider: OAuthProvider) -> None:
        self._providers[name] = provider

    def get(self, name: str) -> OAuthProvider:
        if name not in self._providers:
            raise ValueError(f"OAuth provider not registered: {name}")
        return self._providers[name]

    def names(self) -> list[str]:
        return sorted(self._providers)
