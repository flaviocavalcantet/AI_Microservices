# Jobs API responses module

from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class JobResponse(BaseModel):
    """Job data for API responses"""
    
    id: str
    user_id: Optional[str]
    job_type: str
    status: str
    priority: int
    created_at: str
    completed_at: Optional[str]
    result: Optional[Dict[str, Any]]
    error: Optional[str]


class CreateJobResponse(BaseModel):
    """Response for successful job creation"""
    
    status: str = "success"
    data: JobResponse
    correlation_id: Optional[str]
    timestamp: str


class GetJobResponse(BaseModel):
    """Response for getting a single job"""
    
    status: str = "success"
    data: JobResponse
    correlation_id: Optional[str]
    timestamp: str


class ListJobsResponse(BaseModel):
    """Response for listing jobs"""
    
    status: str = "success"
    data: List[JobResponse]
    pagination: Dict[str, Any]
    correlation_id: Optional[str]
    timestamp: str
