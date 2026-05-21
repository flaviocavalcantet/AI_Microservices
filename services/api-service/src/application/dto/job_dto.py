# Application DTOs for use cases

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class CreateJobDTO(BaseModel):
    """DTO for creating a job (from presentation → application)"""
    
    job_type: str
    input_data: Dict[str, Any]
    priority: int = 5
    timeout_seconds: Optional[int] = None
    user_id: Optional[str] = None


class JobDTO(BaseModel):
    """DTO representing a job (from application → presentation)"""
    
    id: str
    user_id: Optional[str]
    job_type: str
    status: str
    priority: int
    created_at: str
    completed_at: Optional[str]
    result: Optional[Dict[str, Any]]
    error: Optional[str]
