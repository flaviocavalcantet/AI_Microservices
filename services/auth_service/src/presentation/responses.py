"""Standard API response envelope for auth-service."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from flask import g, jsonify


def _correlation_id() -> str:
    return getattr(g, "correlation_id", None) or getattr(g, "request_id", "") or ""


def success_response(
    data: Any,
    *,
    code: int = 200,
    meta: Optional[Dict[str, Any]] = None,
):
    """Build a standardized success JSON response."""
    body: Dict[str, Any] = {
        "status": "success",
        "code": code,
        "data": data,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    cid = _correlation_id()
    if cid:
        body["correlation_id"] = cid
    if meta:
        body["meta"] = meta
    return jsonify(body), code


def error_response(
    message: str,
    *,
    error_code: str = "API_ERROR",
    http_code: int = 400,
    details: Optional[Dict[str, Any]] = None,
):
    """Build a standardized error JSON response."""
    body: Dict[str, Any] = {
        "status": "error",
        "code": http_code,
        "error": {
            "code": error_code,
            "message": message,
            "details": details or {},
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    cid = _correlation_id()
    if cid:
        body["correlation_id"] = cid
    return jsonify(body), http_code
