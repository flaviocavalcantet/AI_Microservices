"""GitHub OAuth2 provider adapter."""

from __future__ import annotations

import logging
from typing import Any, Dict
from urllib.parse import urlencode

import requests

from ...application.ports.interfaces import IOAuthProvider
from ...domain.exceptions.auth_errors import OAuthProviderError

logger = logging.getLogger(__name__)

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


class GitHubOAuthProvider(IOAuthProvider):
    """GitHub OAuth2 + PKCE integration."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: str = "read:user user:email",
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._scopes = scopes

    @property
    def name(self) -> str:
        return "github"

    def build_authorization_url(self, state: str, code_challenge: str) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "scope": self._scopes,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"

    def exchange_code(
        self, code: str, state: str, code_verifier: str
    ) -> Dict[str, Any]:
        token_data = self._exchange_authorization_code(code, code_verifier)
        access_token = token_data.get("access_token")
        if not access_token:
            raise OAuthProviderError("GitHub token response missing access_token")
        return self.get_userinfo(access_token)

    def get_userinfo(self, access_token: str) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
        }
        try:
            user_resp = requests.get(GITHUB_USER_URL, headers=headers, timeout=15)
            user_resp.raise_for_status()
            profile = user_resp.json()

            email = profile.get("email")
            if not email:
                email = self._fetch_primary_email(headers)

            return {
                "provider_user_id": str(profile["id"]),
                "email": email,
                "display_name": profile.get("name") or profile.get("login", ""),
                "avatar_url": profile.get("avatar_url"),
            }
        except requests.RequestException as exc:
            logger.error("GitHub userinfo request failed", extra={"error": str(exc)})
            raise OAuthProviderError(f"Failed to fetch GitHub user profile: {exc}") from exc

    def _exchange_authorization_code(
        self, code: str, code_verifier: str
    ) -> Dict[str, Any]:
        payload = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "code": code,
            "redirect_uri": self._redirect_uri,
            "code_verifier": code_verifier,
        }
        headers = {"Accept": "application/json"}
        try:
            resp = requests.post(
                GITHUB_TOKEN_URL, data=payload, headers=headers, timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise OAuthProviderError(
                    f"GitHub token error: {data.get('error_description', data['error'])}"
                )
            return data
        except requests.RequestException as exc:
            logger.error("GitHub token exchange failed", extra={"error": str(exc)})
            raise OAuthProviderError(f"GitHub code exchange failed: {exc}") from exc

    def _fetch_primary_email(self, headers: Dict[str, str]) -> str:
        resp = requests.get(GITHUB_EMAILS_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        emails = resp.json()
        primary = next(
            (e["email"] for e in emails if e.get("primary") and e.get("verified")),
            None,
        )
        if not primary and emails:
            primary = emails[0].get("email")
        if not primary:
            raise OAuthProviderError("GitHub account has no accessible email")
        return primary
