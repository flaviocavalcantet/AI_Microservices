"""
Job Data Transfer Objects (DTOs)

Pydantic models for type-safe data transfer at layer boundaries.
Used for request/response validation and serialization.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Any, Dict
from datetime import datetime


class CreateJobDTO(BaseModel):
    """
    Input DTO for creating a job.
    
    Validates:
    - job_type: Non-empty string
    - input_data: Dict (can be empty)
    - priority: 1-10
    - timeout_seconds: Positive integer
    - user_id: Non-empty string
    """
    
    job_type: str = Field(..., min_length=1, description="Type of job to execute")
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Job input parameters")
    priority: int = Field(default=5, ge=1, le=10, description="Priority (1-10)")
    timeout_seconds: int = Field(default=3600, ge=1, description="Timeout in seconds")
    user_id: str = Field(..., min_length=1, description="User ID creating the job")
    
    class Config:
        """Pydantic config"""
        schema_extra = {
            "example": {
                "job_type": "model_training",
                "input_data": {"model": "bert", "dataset": "wikitext"},
                "priority": 5,
                "timeout_seconds": 3600,
                "user_id": "user-123",
            }
        }


class JobDTO(BaseModel):
    """
    Output DTO for job representation.
    
    Returned from all job use cases.
    Includes all job state and metadata.
    """
    
    id: str = Field(..., description="Unique job ID")
    user_id: str = Field(..., description="User who created job")
    job_type: str = Field(..., description="Type of job")
    status: str = Field(..., description="Current status: pending, running, completed, failed, cancelled")
    priority: int = Field(..., description="Priority (1-10)")
    created_at: Optional[str] = Field(None, description="ISO-8601 timestamp when created")
    started_at: Optional[str] = Field(None, description="ISO-8601 timestamp when started")
    completed_at: Optional[str] = Field(None, description="ISO-8601 timestamp when completed")
    result: Optional[Dict[str, Any]] = Field(None, description="Job result (if completed)")
    error: Optional[str] = Field(None, description="Error message (if failed)")
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Input parameters")
    timeout_seconds: int = Field(default=3600, description="Timeout in seconds")
    
    class Config:
        """Pydantic config"""
        schema_extra = {
            "example": {
                "id": "job-abc123",
                "user_id": "user-123",
                "job_type": "model_training",
                "status": "running",
                "priority": 5,
                "created_at": "2026-05-21T10:30:00Z",
                "started_at": "2026-05-21T10:30:05Z",
                "completed_at": None,
                "result": None,
                "error": None,
                "input_data": {"model": "bert"},
                "timeout_seconds": 3600,
            }
        }
    
    def dict(self, **kwargs) -> Dict[str, Any]:
        """Override dict() to handle serialization"""
        return super().dict(**kwargs)
