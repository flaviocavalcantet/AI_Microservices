# Common DTOs and response helpers

from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """Query parameters for paginated list endpoints"""
    
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
    
    sort_by: Optional[str] = Field(
        default=None,
        description="Field to sort by"
    )
    
    sort_order: str = Field(
        default="desc",
        pattern="^(asc|desc)$",
        description="Sort order: asc or desc"
    )


class MetaInfo(BaseModel):
    """Metadata for responses"""
    
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    processed_at: Optional[str] = None
    api_version: str = "v1"


class ErrorDetail(BaseModel):
    """Individual error detail"""
    
    code: str = Field(description="Error code")
    message: str = Field(description="Error message")
    field: Optional[str] = None
    expected: Optional[str] = None
    received: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ValidationErrorResponse(BaseModel):
    """Response for validation errors"""
    
    status: str = "error"
    error: str = "Validation failed"
    errors: List[ErrorDetail]
    correlation_id: Optional[str] = None


class NotFoundResponse(BaseModel):
    """Response for 404 errors"""
    
    status: str = "error"
    error: str = "Not found"
    resource: str
    correlation_id: Optional[str] = None


class ConflictResponse(BaseModel):
    """Response for 409 conflict errors"""
    
    status: str = "error"
    error: str = "Conflict"
    details: Dict[str, Any]
    correlation_id: Optional[str] = None
