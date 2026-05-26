"""Authentication API routes — thin controllers delegating to AuthApiService."""

from __future__ import annotations

from flask import Blueprint, redirect, request

from ....middleware.validation import validate_json_body, validate_query_params
from ....responses import success_response
from .....application.dto.auth_dto import TokenResponseDTO
from .....application.use_cases.token_ops import RevokeTokenUseCase, ValidateTokenUseCase
from .....container import resolve_from_context
from .....errors import APIError
from .mappers import oauth_start_response_data, token_response_data
from .schemas import (
    GitHubCallbackQuery,
    GitHubOAuthQuery,
    LoginRequest,
    RefreshTokenRequest,
    RevokeTokenRequest,
    VerifyTokenRequest,
)
from .service import AuthApiService

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")

GITHUB = AuthApiService.PROVIDER_GITHUB


def _api() -> AuthApiService:
    """Resolve per-request — container is populated during app factory."""
    return AuthApiService()


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["POST"])
@validate_json_body(LoginRequest)
def login():
    """
    Start or complete OAuth login
    ---
    tags:
      - Authentication
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        schema:
          type: object
          properties:
            provider:
              type: string
              default: github
            redirect_uri:
              type: string
            code:
              type: string
              description: Authorization code (completion)
            state:
              type: string
              description: CSRF state (completion)
            code_verifier:
              type: string
              description: PKCE verifier (completion)
    responses:
      200:
        description: Tokens issued or OAuth authorization URL returned
      400:
        description: Validation error
      502:
        description: OAuth provider error
    """
    body: LoginRequest = request.validated_data
    result = _api().login(
        provider=body.provider,
        redirect_uri=body.redirect_uri,
        code=body.code,
        state=body.state,
        code_verifier=body.code_verifier,
        ip_address=request.remote_addr or "",
    )
    if isinstance(result, TokenResponseDTO):
        return success_response(token_response_data(result))
    return success_response(oauth_start_response_data(result))


# ---------------------------------------------------------------------------
# POST /api/v1/auth/refresh
# ---------------------------------------------------------------------------

@auth_bp.route("/refresh", methods=["POST"])
@validate_json_body(RefreshTokenRequest)
def refresh():
    """
    Refresh access token using a refresh token
    ---
    tags:
      - Authentication
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - refresh_token
          properties:
            refresh_token:
              type: string
    responses:
      200:
        description: New token pair issued
      401:
        description: Invalid or expired refresh token
    """
    body: RefreshTokenRequest = request.validated_data
    result = _api().refresh(body.refresh_token)
    return success_response(token_response_data(result))


# ---------------------------------------------------------------------------
# GET /api/v1/auth/oauth/github
# ---------------------------------------------------------------------------

@auth_bp.route("/oauth/github", methods=["GET"])
@validate_query_params(GitHubOAuthQuery)
def github_oauth_start():
    """
    Start GitHub OAuth login
    ---
    tags:
      - Authentication
    parameters:
      - name: format
        in: query
        type: string
        enum: [redirect, json]
        default: redirect
        description: redirect sends browser to GitHub; json returns authorization URL
      - name: redirect_uri
        in: query
        type: string
    responses:
      200:
        description: Authorization URL (format=json)
      302:
        description: Redirect to GitHub (format=redirect)
    """
    query: GitHubOAuthQuery = request.validated_query
    result = _api().start_oauth(GITHUB, redirect_uri=query.redirect_uri)

    if query.format == "json":
        return success_response(oauth_start_response_data(result))

    return redirect(result.authorization_url, code=302)


# ---------------------------------------------------------------------------
# GET /api/v1/auth/oauth/github/callback
# ---------------------------------------------------------------------------

@auth_bp.route("/oauth/github/callback", methods=["GET"])
@validate_query_params(GitHubCallbackQuery)
def github_oauth_callback():
    """
    GitHub OAuth callback — exchanges code for platform tokens
    ---
    tags:
      - Authentication
    parameters:
      - name: code
        in: query
        type: string
        required: true
      - name: state
        in: query
        type: string
        required: true
      - name: code_verifier
        in: query
        type: string
    responses:
      200:
        description: Platform access and refresh tokens
      400:
        description: Invalid state or missing PKCE verifier
    """
    query: GitHubCallbackQuery = request.validated_query
    result = _api().complete_oauth(
        provider=GITHUB,
        code=query.code,
        state=query.state,
        code_verifier=query.code_verifier,
        ip_address=request.remote_addr or "",
    )
    return success_response(token_response_data(result))


# ---------------------------------------------------------------------------
# Supplementary endpoints (verify / revoke / logout)
# ---------------------------------------------------------------------------

@auth_bp.route("/token/verify", methods=["POST"])
@validate_json_body(VerifyTokenRequest)
def verify_token():
    """
    Verify an access token
    ---
    tags:
      - Authentication
    """
    body: VerifyTokenRequest = request.validated_data
    use_case = resolve_from_context("validate_token_use_case")
    from .....application.dto.auth_dto import TokenVerifyRequestDTO

    result = use_case.execute(TokenVerifyRequestDTO(token=body.token))
    return success_response(result.dict())


@auth_bp.route("/token/revoke", methods=["POST"])
@validate_json_body(RevokeTokenRequest)
def revoke_token():
    """
    Revoke refresh token session (logout)
    ---
    tags:
      - Authentication
    """
    body: RevokeTokenRequest = request.validated_data
    use_case: RevokeTokenUseCase = resolve_from_context("revoke_token_use_case")
    from .....application.dto.auth_dto import RevokeTokenRequestDTO

    use_case.execute(RevokeTokenRequestDTO(
        refresh_token=body.refresh_token,
        reason=body.reason,
    ))
    return success_response({"revoked": True})


@auth_bp.route("/oauth/<provider>/authorize", methods=["GET"])
def oauth_authorize_legacy(provider: str):
    """Deprecated — use GET /oauth/github."""
    try:
        result = _api().start_oauth(provider, redirect_uri=request.args.get("redirect_uri"))
        return success_response(oauth_start_response_data(result))
    except ValueError as exc:
        raise APIError(str(exc), status_code=400, error_code="PROVIDER_NOT_FOUND") from exc
