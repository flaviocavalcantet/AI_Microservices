"""Request/response schemas for auth API endpoints."""

from typing import Optional

from pydantic import BaseModel, Field, root_validator


class StrictRequestModel(BaseModel):
    class Config:
        extra = "forbid"
        anystr_strip_whitespace = True


class LoginRequest(StrictRequestModel):
    """POST /auth/login — start OAuth or complete with authorization code."""

    provider: str = Field(default="github", description="OAuth provider name")
    redirect_uri: Optional[str] = Field(None, description="Override OAuth redirect URI")
    code: Optional[str] = Field(None, description="Authorization code (completion flow)")
    state: Optional[str] = Field(None, description="CSRF state (completion flow)")
    code_verifier: Optional[str] = Field(None, description="PKCE verifier (completion flow)")

    @root_validator
    def validate_flow(cls, values):
        code = values.get("code")
        state = values.get("state")
        if (code and not state) or (state and not code):
            raise ValueError("Both code and state are required to complete login")
        return values


class RefreshTokenRequest(StrictRequestModel):
    """POST /auth/refresh."""

    refresh_token: str = Field(..., min_length=1, description="Opaque refresh token")


class RevokeTokenRequest(StrictRequestModel):
    """POST /auth/token/revoke (internal/logout)."""

    refresh_token: str = Field(..., min_length=1)
    reason: str = Field(default="user_logout")


class VerifyTokenRequest(StrictRequestModel):
    """POST /auth/token/verify."""

    token: str = Field(..., min_length=1)


class GitHubOAuthQuery(StrictRequestModel):
    """GET /auth/oauth/github query parameters."""

    redirect_uri: Optional[str] = None
    format: str = Field(default="redirect", description="redirect or json")

    @root_validator
    def validate_format(cls, values):
        fmt = values.get("format", "redirect")
        if fmt not in ("redirect", "json"):
            raise ValueError("format must be 'redirect' or 'json'")
        return values


class GitHubCallbackQuery(StrictRequestModel):
    """GET /auth/oauth/github/callback query parameters."""

    code: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)
    code_verifier: Optional[str] = Field(None, description="Optional if stored server-side")
