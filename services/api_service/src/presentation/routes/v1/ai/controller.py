"""
AI Processing API Blueprint Controller

Implements AI processing endpoints:
- POST /api/v1/ai/summarize  – Submit text summarization job
- POST /api/v1/ai/sentiment  – Submit sentiment analysis job
- POST /api/v1/ai/profile    – Submit dataset profiling job

Job status and results are retrieved via the standard jobs endpoint:
- GET  /api/v1/jobs/{job_id} – Retrieve job status (see jobs controller)

The controller follows REST conventions:
1. Validates incoming requests against Pydantic schemas (via @validate_json_body)
2. Delegates to use cases (application layer)
3. Transforms responses into standardized envelopes
4. Converts exceptions into appropriate HTTP error responses
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from flask import Blueprint, jsonify, request

from services.api_service.src.application.use_cases.ai_processing import (
    SubmitProfileUseCase,
    SubmitSentimentUseCase,
    SubmitSummarizeUseCase,
)
from services.api_service.src.container import resolve_from_context
from services.api_service.src.logger import get_logger
from services.api_service.src.presentation.middleware.validation import (
    validate_json_body,
)
from services.api_service.src.presentation.routes.v1.ai.schemas import (
    AcceptedResponse,
    ProfileRequest,
    SentimentRequest,
    SummarizeRequest,
)

logger = get_logger(__name__)

ai_bp = Blueprint(
    name="ai",
    import_name=__name__,
    url_prefix="/api/v1/ai",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_request_base_url() -> str:
    """Extract the base URL (scheme + host) from the current request."""
    return f"{request.scheme}://{request.host}"


def _format_error_response(code: int, error_code: str, message: str, details: Dict[str, Any] = None) -> Dict[str, Any]:
    """Format a standardized error response."""
    error_detail = {
        "code": error_code,
        "message": message,
    }
    if details:
        error_detail["details"] = details
    
    return {
        "status": "error",
        "code": code,
        "error": error_detail,
    }


# ---------------------------------------------------------------------------
# POST /api/v1/ai/summarize
# ---------------------------------------------------------------------------

@ai_bp.route("/summarize", methods=["POST"])
@validate_json_body(SummarizeRequest)
def submit_summarize():
    """
    Submit a text summarization job.

    Request body (Pydantic validated):
        text: str (required, ≥20 words) – Document to summarize
        max_new_tokens: int (optional, 1-1024) – Max summary length
        min_new_tokens: int (optional, 1-512) – Min summary length
        tags: dict (optional) – Key-value labels for filtering

    Returns 202 Accepted with job_id, status='pending', and poll_url.
    On validation error (400), includes structured field-level errors.

    Example request:
        {
            "text": "Artificial intelligence...",
            "max_new_tokens": 150,
            "tags": {"tenant": "acme"}
        }

    Example response (202):
        {
            "status": "success",
            "code": 202,
            "data": {
                "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "status": "pending",
                "poll_url": "/api/v1/jobs/3fa85f64-5717-4562-b3fc-2c963f66afa6"
            }
        }
    """
    try:
        data: SummarizeRequest = request.validated_data
        use_case: SubmitSummarizeUseCase = resolve_from_context("submit_summarize_use_case")

        response_dict = use_case.execute(
            text=data.text,
            max_new_tokens=data.max_new_tokens,
            min_new_tokens=data.min_new_tokens,
            tags=data.tags,
            base_url=_get_request_base_url(),
        )

        logger.info(
            "Summarization job submitted",
            extra={"job_id": response_dict["job_id"], "word_count": len(data.text.split())},
        )

        # Build and return 202 Accepted response
        response = AcceptedResponse(
            status="success",
            code=202,
            data={
                "job_id": response_dict["job_id"],
                "status": "pending",
                "poll_url": response_dict["poll_url"],
            },
        )
        return jsonify(response.dict()), 202

    except ValueError as exc:
        logger.warning(f"Validation error in submit_summarize: {exc}")
        return jsonify(_format_error_response(400, "VALIDATION_ERROR", str(exc))), 400
    except Exception as exc:
        logger.error(f"Error submitting summarization job: {exc}", exc_info=True)
        return jsonify(_format_error_response(500, "INTERNAL_ERROR", "Failed to submit job")), 500


# ---------------------------------------------------------------------------
# POST /api/v1/ai/sentiment
# ---------------------------------------------------------------------------

@ai_bp.route("/sentiment", methods=["POST"])
@validate_json_body(SentimentRequest)
def submit_sentiment():
    """
    Submit a sentiment analysis job.

    Request body (Pydantic validated):
        text: str (required, ≥3 chars) – Text to classify
        neutral_threshold: float (optional, 0.0-1.0) – Confidence threshold
        tags: dict (optional) – Key-value labels for filtering

    Returns 202 Accepted with job_id, status='pending', and poll_url.

    Example request:
        {
            "text": "The new product launch exceeded all expectations!",
            "neutral_threshold": 0.15,
            "tags": {"tenant": "acme"}
        }

    Example response (202):
        {
            "status": "success",
            "code": 202,
            "data": {
                "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "status": "pending",
                "poll_url": "/api/v1/jobs/3fa85f64-5717-4562-b3fc-2c963f66afa6"
            }
        }
    """
    try:
        data: SentimentRequest = request.validated_data
        use_case: SubmitSentimentUseCase = resolve_from_context("submit_sentiment_use_case")

        response_dict = use_case.execute(
            text=data.text,
            neutral_threshold=data.neutral_threshold,
            tags=data.tags,
            base_url=_get_request_base_url(),
        )

        logger.info(
            "Sentiment analysis job submitted",
            extra={"job_id": response_dict["job_id"], "char_count": len(data.text)},
        )

        # Build and return 202 Accepted response
        response = AcceptedResponse(
            status="success",
            code=202,
            data={
                "job_id": response_dict["job_id"],
                "status": "pending",
                "poll_url": response_dict["poll_url"],
            },
        )
        return jsonify(response.dict()), 202

    except ValueError as exc:
        logger.warning(f"Validation error in submit_sentiment: {exc}")
        return jsonify(_format_error_response(400, "VALIDATION_ERROR", str(exc))), 400
    except Exception as exc:
        logger.error(f"Error submitting sentiment job: {exc}", exc_info=True)
        return jsonify(_format_error_response(500, "INTERNAL_ERROR", "Failed to submit job")), 500


# ---------------------------------------------------------------------------
# POST /api/v1/ai/profile
# ---------------------------------------------------------------------------

@ai_bp.route("/profile", methods=["POST"])
@validate_json_body(ProfileRequest)
def submit_profile():
    """
    Submit a dataset profiling job.

    Request body (Pydantic validated):
        data: str | list (required) – CSV string or list of JSON objects
        input_type: 'csv' | 'json' | 'auto' (optional) – Input format hint
        tags: dict (optional) – Key-value labels for filtering

    Returns 202 Accepted with job_id, status='pending', and poll_url.

    Example request (CSV):
        {
            "data": "name,age,score\\nAlice,30,9.5\\nBob,,7.0",
            "input_type": "csv",
            "tags": {"project": "analysis"}
        }

    Example request (JSON):
        {
            "data": [{"name": "Alice", "age": 30}, {"name": "Bob"}],
            "input_type": "json",
            "tags": {"project": "analysis"}
        }

    Example response (202):
        {
            "status": "success",
            "code": 202,
            "data": {
                "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "status": "pending",
                "poll_url": "/api/v1/jobs/3fa85f64-5717-4562-b3fc-2c963f66afa6"
            }
        }
    """
    try:
        data: ProfileRequest = request.validated_data
        use_case: SubmitProfileUseCase = resolve_from_context("submit_profile_use_case")

        response_dict = use_case.execute(
            data=data.data,
            input_type=data.input_type,
            tags=data.tags,
            base_url=_get_request_base_url(),
        )

        logger.info(
            "Dataset profiling job submitted",
            extra={"job_id": response_dict["job_id"]},
        )

        # Build and return 202 Accepted response
        response = AcceptedResponse(
            status="success",
            code=202,
            data={
                "job_id": response_dict["job_id"],
                "status": "pending",
                "poll_url": response_dict["poll_url"],
            },
        )
        return jsonify(response.dict()), 202

    except ValueError as exc:
        logger.warning(f"Validation error in submit_profile: {exc}")
        return jsonify(_format_error_response(400, "VALIDATION_ERROR", str(exc))), 400
    except Exception as exc:
        logger.error(f"Error submitting profiling job: {exc}", exc_info=True)
        return jsonify(_format_error_response(500, "INTERNAL_ERROR", "Failed to submit job")), 500
