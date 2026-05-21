# Jobs API request and response schemas

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
from datetime import datetime


class CreateJobRequest(BaseModel):
    """Request to create a new job
    
    Example:
        {
            "job_type": "model_training",
            "input_data": {
                "model_name": "bert-base",
                "learning_rate": 0.001
            },
            "priority": 5
        }
    """
    
    job_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Type of job (e.g., model_training, inference)"
    )
    
    input_data: Dict[str, Any] = Field(
        ...,
        description="Input parameters for the job"
    )
    
    priority: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Priority level (1=lowest, 10=highest)"
    )
    
    timeout_seconds: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum execution time in seconds"
    )
    
    @validator("job_type")
    def validate_job_type(cls, v):
        """Validate job type is valid"""
        valid_types = ["model_training", "inference", "evaluation", "preprocessing"]
        if v not in valid_types:
            raise ValueError(f"Invalid job type. Must be one of: {valid_types}")
        return v


class UpdateJobRequest(BaseModel):
    """Request to update a job (future use)"""
    
    priority: Optional[int] = Field(None, ge=1, le=10)
    status: Optional[str] = None


class ListJobsQuery(BaseModel):
    """Query parameters for listing jobs"""
    
    limit: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Items per page"
    )
    
    offset: int = Field(
        default=0,
        ge=0,
        description="Starting position"
    )
    
    status: Optional[str] = Field(
        default=None,
        description="Filter by status (pending, running, completed, failed)"
    )
    
    job_type: Optional[str] = Field(
        default=None,
        description="Filter by job type"
    )
    
    sort_by: str = Field(
        default="created_at",
        description="Sort by field"
    )
    
    sort_order: str = Field(
        default="desc",
        pattern="^(asc|desc)$",
        description="Sort order"
    )


# Response schemas
class JobResponse(BaseModel):
    """Job response model"""
    
    id: str
    user_id: Optional[str] = None
    job_type: str
    status: str
    priority: int
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "id": "job-123",
                "user_id": "user-456",
                "job_type": "model_training",
                "status": "running",
                "priority": 5,
                "created_at": "2026-05-20T10:30:45Z",
                "completed_at": None,
                "result": None,
                "error": None
            }
        }


class JobListResponse(BaseModel):
    """List of jobs with pagination"""
    
    status: str = "success"
    data: list[JobResponse]
    pagination: Dict[str, Any]
    timestamp: str


class JobCreatedResponse(BaseModel):
    """Response when job is created"""
    
    status: str = "success"
    data: JobResponse
    timestamp: str
