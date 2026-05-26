"""Application layer DTOs for auth-service.

Pydantic models used at layer boundaries.
No domain entities cross into the presentation layer — only DTOs.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class OAuthLoginRequestDTO(BaseModel):
    provider: str = Field(..., description="OAuth provider name, e.g. 'github'")
    redirect_uri: Optional[str] = Field(None, description="Override redirect URI")


class OAuthCallbackDTO(BaseModel):
    code: str = Field(..., description="Authorization code from OAuth provider")
    state: str = Field(..., description="CSRF state nonce")
    code_verifier: str = Field(..., description="PKCE code verifier")


class TokenResponseDTO(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(..., description="Access token TTL in seconds")
    scope: str = "openid profile email"


class RefreshTokenRequestDTO(BaseModel):
    refresh_token: str = Field(..., description="Opaque refresh token")


class RevokeTokenRequestDTO(BaseModel):
    refresh_token: str = Field(..., description="Refresh token to revoke")
    reason: Optional[str] = Field("user_logout", description="Revocation reason")


class TokenVerifyRequestDTO(BaseModel):
    token: str = Field(..., description="Access token to verify")


class TokenVerifyResponseDTO(BaseModel):
    valid: bool
    user_id: Optional[str] = None
    email: Optional[str] = None
    roles: Optional[List[str]] = None
    expires_at: Optional[str] = None
    error: Optional[str] = None


class UserClaimsDTO(BaseModel):
    user_id: str
    email: str
    display_name: Optional[str]
    roles: List[str]
    provider: str
    session_id: str


class AuthorizationURLResponseDTO(BaseModel):
    authorization_url: str
    state: str
    code_challenge: str
    provider: str
    code_verifier: Optional[str] = Field(
        None,
        description="PKCE verifier — returned only when initiating login (store client-side)",
    )
