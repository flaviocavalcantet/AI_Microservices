# Presentation layer DTOs and response models

from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List, Generic, TypeVar
from datetime import datetime


class BaseResponse(BaseModel):
    """Base response envelope for all API responses
    
    All API responses follow this structure:
    {
        "status": "success",
        "timestamp": "2026-05-20T10:30:45Z",
        "correlation_id": "abc-123",
        "data": {...}
    }
    """
    
    status: str = Field(
        default="success",
        description="Response status: success or error"
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp of response"
    )
    
    correlation_id: Optional[str] = Field(
        default=None,
        description="Correlation ID for distributed tracing"
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() + 'Z' if v else None
        }


T = TypeVar('T')


class DataResponse(BaseResponse, Generic[T]):
    """Response with single data object
    
    Used for single resource responses (get, create, update)
    """
    
    data: Optional[T] = Field(
        default=None,
        description="Response data"
    )


class ListResponse(BaseResponse, Generic[T]):
    """Response with paginated list
    
    Used for list endpoints with pagination
    """
    
    data: List[T] = Field(
        default_factory=list,
        description="List of items"
    )
    
    pagination: Dict[str, Any] = Field(
        default_factory=dict,
        description="Pagination metadata"
    )
    
    meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )


class PaginationInfo(BaseModel):
    """Pagination metadata"""
    
    limit: int = Field(description="Items per page")
    offset: int = Field(description="Starting position")
    total: int = Field(description="Total items")
    page: int = Field(description="Current page number")
    pages: int = Field(description="Total pages")


class ErrorResponse(BaseResponse):
    """Error response envelope
    
    {
        "status": "error",
        "timestamp": "2026-05-20T10:30:45Z",
        "correlation_id": "abc-123",
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Invalid job type",
            "details": {...}
        }
    }
    """
    
    status: str = "error"
    
    error: Dict[str, Any] = Field(
        description="Error details"
    )


class HealthResponse(BaseModel):
    """Health check response"""
    
    status: str = Field(description="healthy, unhealthy, ready, not_ready, alive")
    service: str = Field(description="Service name")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: Optional[str] = None
    uptime_seconds: Optional[int] = None
    dependencies: Optional[Dict[str, str]] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() + 'Z' if v else None
        }
