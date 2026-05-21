"""Jobs API request schemas."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, root_validator, validator

from services.api_service.src.domain.value_objects.job_status import JobStatus


class StrictRequestModel(BaseModel):
    """Base model for API requests that rejects unknown fields."""

    class Config:
        extra = "forbid"
        anystr_strip_whitespace = True


class CreateJobRequest(StrictRequestModel):
    """Request body for creating a job."""

    job_type: str = Field(..., min_length=1, max_length=100)
    input_data: Dict[str, Any] = Field(...)
    priority: int = Field(default=5, ge=1, le=10)
    timeout_seconds: int = Field(default=3600, ge=1, le=86400)

    @validator("job_type")
    def validate_job_type(cls, value: str) -> str:
        if not value:
            raise ValueError("job_type must not be blank")
        return value


class UpdateJobRequest(StrictRequestModel):
    """Request body for updating a job."""

    priority: Optional[int] = Field(default=None, ge=1, le=10)

    @root_validator
    def require_update_field(cls, values):
        if values.get("priority") is None:
            raise ValueError("At least one updatable field is required")
        return values


class ListJobsQuery(StrictRequestModel):
    """Query parameters for listing jobs."""

    user_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    status: Optional[str] = Field(default=None)
    job_type: Optional[str] = Field(default=None, min_length=1, max_length=100)
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default="created_at")
    sort_order: str = Field(default="desc")

    @validator("status")
    def validate_status(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not JobStatus.is_valid(value):
            valid = ", ".join(JobStatus.VALID_STATUSES)
            raise ValueError(f"status must be one of: {valid}")
        return value

    @validator("sort_by")
    def validate_sort_by(cls, value: str) -> str:
        valid_fields = {"created_at", "status", "priority"}
        if value not in valid_fields:
            raise ValueError("sort_by must be one of: created_at, status, priority")
        return value

    @validator("sort_order")
    def validate_sort_order(cls, value: str) -> str:
        if value not in {"asc", "desc"}:
            raise ValueError("sort_order must be one of: asc, desc")
        return value


class JobPathParams(StrictRequestModel):
    """Path parameters for routes that address one job."""

    job_id: str = Field(..., min_length=1, max_length=128)
