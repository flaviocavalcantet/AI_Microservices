"""Shared fixtures for auth-service API tests."""

import pytest

from services.auth_service.src.container import get_container
from services.auth_service.src.infrastructure.security.oauth_registry import OAuthProviderRegistry
from services.auth_service.src.presentation.app import create_app


class FakeGitHubProvider:
    name = "github"

    def build_authorization_url(self, state: str, code_challenge: str) -> str:
        return f"https://github.example/oauth?state={state}&challenge={code_challenge}"

    def exchange_code(self, code: str, state: str, code_verifier: str) -> dict:
        return {
            "provider_user_id": "gh-test-1",
            "email": "oauth-test@example.com",
            "display_name": "OAuth Test",
            "avatar_url": None,
        }

    def get_userinfo(self, access_token: str) -> dict:
        return self.exchange_code("", "", "")


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "test-client-secret")
    application = create_app()
    registry: OAuthProviderRegistry = get_container().resolve("oauth_provider_registry")
    registry.register("github", FakeGitHubProvider())
    return application


@pytest.fixture
def client(app):
    return app.test_client()
