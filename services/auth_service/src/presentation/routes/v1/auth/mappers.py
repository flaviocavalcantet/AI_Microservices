"""Map application DTOs to API response shapes."""

from __future__ import annotations

from typing import Any, Dict

from .....application.dto.auth_dto import AuthorizationURLResponseDTO, TokenResponseDTO


def token_response_data(dto: TokenResponseDTO) -> Dict[str, Any]:
    return {
        "access_token": dto.access_token,
        "refresh_token": dto.refresh_token,
        "token_type": dto.token_type,
        "expires_in": dto.expires_in,
        "scope": dto.scope,
    }


def oauth_start_response_data(dto: AuthorizationURLResponseDTO) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "authorization_url": dto.authorization_url,
        "state": dto.state,
        "code_challenge": dto.code_challenge,
        "provider": dto.provider,
    }
    if dto.code_verifier:
        data["code_verifier"] = dto.code_verifier
    return data
