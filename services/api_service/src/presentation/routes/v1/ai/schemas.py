"""
Request and response schemas for the AI processing endpoints.

Each Pydantic model serves three purposes simultaneously:
1. Runtime validation of incoming JSON (Pydantic raises ValidationError on bad data)
2. OpenAPI schema generation (flasgger reads the docstrings + Config.schema_extra)
3. Type-safe data transfer between the controller and the use-case layer

Models are grouped by endpoint:
  Summarization  – SummarizeRequest
  Sentiment      – SentimentRequest
  Profiling      – ProfileRequest
  Shared 202     – AcceptedResponse / AcceptedData
  Shared GET     – AIJobResponse / AIJobData / AIJobResultData
  Errors         – ValidationFieldError / ErrorDetail / ErrorResponse
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, validator


# ---------------------------------------------------------------------------
# Base request model
# ---------------------------------------------------------------------------

class StrictRequest(BaseModel):
    """Base for all request models — rejects unknown fields."""

    class Config:
        extra = "forbid"
        anystr_strip_whitespace = True


# ---------------------------------------------------------------------------
# Error shapes (reused across all endpoints)
# ---------------------------------------------------------------------------

class ValidationFieldError(BaseModel):
    """Single field-level validation failure."""

    field: str = Field(..., description="Dot-separated field path, e.g. 'text'")
    message: str = Field(..., description="Human-readable description of the failure")
    type: str = Field(..., description="Pydantic error type code, e.g. 'value_error.missing'")


class ErrorDetail(BaseModel):
    """Structured error payload nested inside the standard error envelope."""

    code: str = Field(..., description="Machine-readable error code, e.g. 'VALIDATION_ERROR'")
    message: str = Field(..., description="Human-readable summary")
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional extra context; validation errors include 'validation_errors' list",
    )


class ErrorResponse(BaseModel):
    """Standard error envelope returned on all 4xx / 5xx responses."""

    status: Literal["error"] = "error"
    code: int = Field(..., description="HTTP status code mirrored in the body")
    error: ErrorDetail

    class Config:
        schema_extra = {
            "example": {
                "status": "error",
                "code": 422,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request body",
                    "details": {
                        "validation_errors": [
                            {
                                "field": "text",
                                "message": "field required",
                                "type": "value_error.missing",
                            }
                        ]
                    },
                },
            }
        }


# ---------------------------------------------------------------------------
# 202 Accepted — shared by all three POST AI endpoints
# ---------------------------------------------------------------------------

class AcceptedData(BaseModel):
    """Payload inside the 202 Accepted envelope."""

    job_id: str = Field(..., description="UUID of the newly created AI job")
    status: Literal["pending"] = Field(
        "pending", description="Always 'pending' at submission time"
    )
    poll_url: str = Field(
        ..., description="URL to GET for job status and result"
    )


class AcceptedResponse(BaseModel):
    """202 Accepted — returned immediately by all three AI submission endpoints."""

    status: Literal["success"] = "success"
    code: Literal[202] = 202
    data: AcceptedData

    class Config:
        schema_extra = {
            "example": {
                "status": "success",
                "code": 202,
                "data": {
                    "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "status": "pending",
                    "poll_url": "/api/v1/jobs/3fa85f64-5717-4562-b3fc-2c963f66afa6",
                },
            }
        }


# ---------------------------------------------------------------------------
# POST /api/v1/ai/summarize
# ---------------------------------------------------------------------------

class SummarizeRequest(StrictRequest):
    """
    Request body for text summarization.

    The text is passed to a HuggingFace abstractive summarization model.
    Texts between 20 and 50,000 words are accepted.
    """

    text: str = Field(
        ...,
        min_length=1,
        description="Document to summarise. Must contain at least 20 words.",
        example=(
            "Artificial intelligence has transformed the way we interact with computers. "
            "Modern language models understand context, generate coherent text, and assist "
            "with tasks ranging from writing to code generation. This shift has far-reaching "
            "implications for education, business, and society at large."
        ),
    )
    max_new_tokens: Optional[int] = Field(
        default=None,
        ge=1,
        le=1024,
        description="Maximum tokens in the summary. Defaults to the model preset (150).",
    )
    min_new_tokens: Optional[int] = Field(
        default=None,
        ge=1,
        le=512,
        description="Minimum tokens in the summary. Defaults to the model preset (30).",
    )
    tags: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional key-value labels attached to the job for filtering.",
        example={"tenant": "acme", "project": "newsletter"},
    )

    @validator("text")
    def text_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be blank")
        return v

    @validator("min_new_tokens", always=True)
    def min_le_max(cls, min_val: Optional[int], values: dict) -> Optional[int]:
        max_val = values.get("max_new_tokens")
        if min_val is not None and max_val is not None and min_val > max_val:
            raise ValueError(
                "min_new_tokens must be less than or equal to max_new_tokens"
            )
        return min_val

    class Config:
        schema_extra = {
            "example": {
                "text": "Artificial intelligence has transformed how we interact with computers...",
                "max_new_tokens": 150,
                "min_new_tokens": 30,
                "tags": {"tenant": "acme", "project": "newsletter"},
            }
        }


# ---------------------------------------------------------------------------
# POST /api/v1/ai/sentiment
# ---------------------------------------------------------------------------

class SentimentRequest(StrictRequest):
    """
    Request body for sentiment analysis.

    The classifier returns 'positive', 'negative', or 'neutral'.
    Texts up to 10,000 words are accepted; the underlying model clips at
    512 tokens and sets `input_truncated: true` in the result.
    """

    text: str = Field(
        ...,
        min_length=3,
        description="Text to classify. Minimum 3 characters.",
        example="The new product launch exceeded all expectations. Customers loved it!",
    )
    neutral_threshold: Optional[float] = Field(
        default=None,
        ge=0.0,
        lt=1.0,
        description=(
            "When the winning label's confidence is below this threshold the result "
            "is overridden to 'neutral'. Set to 0.0 (default) to disable neutral band."
        ),
    )
    tags: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional key-value labels for job filtering.",
    )

    @validator("text")
    def text_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be blank")
        return v

    class Config:
        schema_extra = {
            "example": {
                "text": "The new product launch exceeded all expectations!",
                "neutral_threshold": 0.15,
                "tags": {"tenant": "acme"},
            }
        }


# ---------------------------------------------------------------------------
# POST /api/v1/ai/profile
# ---------------------------------------------------------------------------

class ProfileRequest(StrictRequest):
    """
    Request body for dataset profiling.

    Accepts either a CSV string (headers on first row) or a list of flat
    JSON objects (one dict per row). Input type is auto-detected from the
    Python type of `data` when `input_type` is 'auto' or omitted.
    """

    data: Union[str, List[Dict[str, Any]]] = Field(
        ...,
        description=(
            "Dataset to profile. Either a CSV string or a list of flat JSON objects."
        ),
    )
    input_type: Optional[Literal["csv", "json", "auto"]] = Field(
        default="auto",
        description=(
            "'csv' forces CSV parsing, 'json' forces record parsing, "
            "'auto' detects from the data type (default)."
        ),
    )
    tags: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional key-value labels for job filtering.",
    )

    @validator("data")
    def data_not_empty(cls, v: Union[str, list]) -> Union[str, list]:
        if isinstance(v, str) and not v.strip():
            raise ValueError("CSV data must not be blank")
        if isinstance(v, list) and len(v) == 0:
            raise ValueError("JSON records list must not be empty")
        return v

    @validator("input_type", always=True)
    def input_type_consistent_with_data(
        cls, input_type: Optional[str], values: dict
    ) -> Optional[str]:
        data = values.get("data")
        if data is None:
            return input_type
        if input_type == "csv" and not isinstance(data, str):
            raise ValueError("input_type='csv' requires data to be a string")
        if input_type == "json" and not isinstance(data, list):
            raise ValueError("input_type='json' requires data to be a list")
        return input_type

    class Config:
        schema_extra = {
            "example": {
                "data": "name,age,score\nAlice,30,9.5\nBob,,7.0\nCarol,25,8.0",
                "input_type": "csv",
                "tags": {"project": "customer-analysis"},
            }
        }


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/{job_id} — response schema
# ---------------------------------------------------------------------------

class AIJobResultData(BaseModel):
    """Task-specific output nested inside AIJobData.result once completed."""

    success: bool
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AIJobData(BaseModel):
    """Job state payload nested inside AIJobResponse.data."""

    job_id: str
    job_type: str
    status: str = Field(
        ...,
        description="One of: pending, running, completed, failed, cancelled",
    )
    created_at: str = Field(..., description="ISO-8601 UTC timestamp")
    updated_at: str = Field(..., description="ISO-8601 UTC timestamp")
    result: Optional[AIJobResultData] = Field(
        default=None,
        description="Populated once the job reaches a terminal state",
    )
    tags: Dict[str, str] = Field(default_factory=dict)


class AIJobResponse(BaseModel):
    """
    Response envelope for GET /api/v1/jobs/{job_id}.

    While in progress: result is null, status is 'pending' or 'running'.
    On completion: status is 'completed'/'failed'/'cancelled', result is set.
    """

    status: Literal["success"] = "success"
    code: Literal[200] = 200
    data: AIJobData

    class Config:
        schema_extra = {
            "example": {
                "status": "success",
                "code": 200,
                "data": {
                    "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "job_type": "summarization",
                    "status": "completed",
                    "created_at": "2026-05-21T10:30:00Z",
                    "updated_at": "2026-05-21T10:30:08Z",
                    "result": {
                        "success": True,
                        "data": {
                            "summary": "AI has transformed human-computer interaction.",
                            "original_word_count": 68,
                            "summary_word_count": 8,
                            "compression_ratio": 0.12,
                            "truncated": False,
                        },
                        "error": None,
                        "metadata": {
                            "model_name": "sshleifer/distilbart-cnn-12-6",
                            "latency_ms": 312.5,
                        },
                    },
                    "tags": {"tenant": "acme"},
                },
            }
        }
