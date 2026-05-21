"""
Jobs API Blueprint Controller

Implements all job-related endpoints:
- POST   /api/v1/jobs           - Create job
- GET    /api/v1/jobs           - List jobs  
- GET    /api/v1/jobs/{id}      - Get job
- PUT    /api/v1/jobs/{id}      - Update job
- DELETE /api/v1/jobs/{id}      - Delete job
- POST   /api/v1/jobs/{id}/cancel - Cancel job
"""

import logging
from flask import Blueprint, request, jsonify, g
from datetime import datetime

from services.api_service.src.logger import get_logger
from services.api_service.src.container import resolve_from_context
from services.api_service.src.application.dto.job_dto import CreateJobDTO
from services.api_service.src.application.use_cases.job import (
    CreateJobUseCase,
    ListJobsUseCase,
    GetJobUseCase,
    UpdateJobUseCase,
    CancelJobUseCase,
    DeleteJobUseCase,
)
from services.api_service.src.application.exceptions import (
    JobNotFoundError,
    InvalidJobStatusError,
)
from services.api_service.src.presentation.middleware.validation import (
    validate_json_body,
    validate_path_params,
    validate_query_params,
)
from services.api_service.src.presentation.routes.v1.jobs.schemas import (
    CreateJobRequest,
    JobPathParams,
    ListJobsQuery,
    UpdateJobRequest,
)


logger = get_logger(__name__)

# Create Blueprint
jobs_bp = Blueprint(
    name="jobs",
    import_name=__name__,
    url_prefix="/api/v1/jobs",
)


# Helper functions
def _get_user_id():
    """Get user ID from request context (from auth middleware)."""
    return getattr(g, "user_id", None) or "anonymous"


def _get_is_admin():
    """Get admin flag from request context."""
    return getattr(g, "is_admin", False)


def _resolve_use_case(use_case_name):
    """Resolve use case from service container."""
    return resolve_from_context(use_case_name)


def _format_response(success: bool, data=None, error=None, status="success", code=200):
    """Format standard API response."""
    response_data = {
        "status": status,
        "code": code,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    if data is not None:
        response_data["data"] = data
    if error is not None:
        response_data["error"] = error
    return response_data


# ============================================================================
# POST /api/v1/jobs - Create Job
# ============================================================================

@jobs_bp.route("", methods=["POST"])
@validate_json_body(CreateJobRequest)
def create_job():
    """
    Create a new job.
    
    Request body:
    {
        "job_type": "model_training",     # Required
        "input_data": {...},               # Required
        "priority": 5,                     # Optional (1-10, default 5)
        "timeout_seconds": 3600            # Optional (seconds)
    }
    
    Response:
    {
        "status": "success",
        "code": 201,
        "data": {
            "id": "job-123",
            "job_type": "model_training",
            "status": "pending",
            ...
        }
    }
    """
    try:
        logger.debug("Creating job", extra={"method": "POST", "path": "/api/v1/jobs"})
        
        data = request.validated_data
        
        # Create DTO
        create_dto = CreateJobDTO(
            job_type=data.job_type,
            input_data=data.input_data,
            priority=data.priority,
            timeout_seconds=data.timeout_seconds,
            user_id=_get_user_id(),
        )
        
        # Execute use case
        use_case = _resolve_use_case("create_job_use_case")
        job_dto = use_case.execute(create_dto)
        
        logger.info(
            "Job created successfully",
            extra={
                "job_id": job_dto.id,
                "user_id": job_dto.user_id,
                "job_type": job_dto.job_type,
            }
        )
        
        return jsonify(_format_response(
            success=True,
            data=job_dto.dict(),
            status="success",
            code=201
        )), 201
    
    except ValueError as e:
        logger.warning(f"Validation error in create_job: {e}")
        return jsonify(_format_response(
            success=False,
            status="error",
            code=400,
            error=str(e)
        )), 400
    
    except Exception as e:
        logger.error(f"Error creating job: {e}", exc_info=True)
        return jsonify(_format_response(
            success=False,
            status="error",
            code=500,
            error="Internal server error"
        )), 500


# ============================================================================
# GET /api/v1/jobs - List Jobs
# ============================================================================

@jobs_bp.route("", methods=["GET"])
@validate_query_params(ListJobsQuery)
def list_jobs():
    """
    List jobs with optional filtering and pagination.
    
    Query parameters:
    - user_id: Filter by user (default: current user)
    - status: Filter by status (pending, running, completed, failed, cancelled)
    - job_type: Filter by job type
    - limit: Results per page (default: 10, max: 100)
    - offset: Starting position (default: 0)
    - sort_by: Sort field (created_at, status, priority; default: created_at)
    - sort_order: Sort direction (asc, desc; default: desc)
    
    Response:
    {
        "status": "success",
        "data": {
            "jobs": [...],
            "total": 100,
            "limit": 10,
            "offset": 0
        }
    }
    """
    try:
        logger.debug("Listing jobs", extra={"method": "GET", "path": "/api/v1/jobs"})
        
        query = request.validated_query
        user_id = query.user_id or _get_user_id()
        
        # Execute use case
        use_case = _resolve_use_case("list_jobs_use_case")
        job_dtos, total = use_case.execute(
            user_id=user_id,
            status=query.status,
            job_type=query.job_type,
            limit=query.limit,
            offset=query.offset,
            sort_by=query.sort_by,
            sort_order=query.sort_order,
        )
        
        logger.info(
            "Listed jobs successfully",
            extra={
                "count": len(job_dtos),
                "total": total,
                "user_id": user_id,
                "status": query.status,
            }
        )
        
        return jsonify(_format_response(
            success=True,
            data={
                "jobs": [job.dict() for job in job_dtos],
                "total": total,
                "limit": query.limit,
                "offset": query.offset,
            },
            status="success",
            code=200
        )), 200
    
    except ValueError as e:
        logger.warning(f"Validation error in list_jobs: {e}")
        return jsonify(_format_response(
            success=False,
            status="error",
            code=400,
            error=str(e)
        )), 400
    
    except Exception as e:
        logger.error(f"Error listing jobs: {e}", exc_info=True)
        return jsonify(_format_response(
            success=False,
            status="error",
            code=500,
            error="Internal server error"
        )), 500


# ============================================================================
# GET /api/v1/jobs/{job_id} - Get Job
# ============================================================================

@jobs_bp.route("/<job_id>", methods=["GET"])
@validate_path_params(JobPathParams)
def get_job(job_id):
    """
    Get a single job by ID.
    
    Response:
    {
        "status": "success",
        "data": {
            "id": "job-123",
            "job_type": "model_training",
            "status": "pending",
            ...
        }
    }
    """
    try:
        logger.debug(f"Getting job: {job_id}")
        
        # Execute use case
        use_case = _resolve_use_case("get_job_use_case")
        job_dto = use_case.execute(job_id)
        
        logger.info(
            "Retrieved job successfully",
            extra={"job_id": job_id, "status": job_dto.status}
        )
        
        return jsonify(_format_response(
            success=True,
            data=job_dto.dict(),
            status="success",
            code=200
        )), 200
    
    except JobNotFoundError:
        logger.info(f"Job not found: {job_id}")
        return jsonify(_format_response(
            success=False,
            status="error",
            code=404,
            error=f"Job '{job_id}' not found"
        )), 404
    
    except ValueError as e:
        logger.warning(f"Validation error in get_job: {e}")
        return jsonify(_format_response(
            success=False,
            status="error",
            code=400,
            error=str(e)
        )), 400
    
    except Exception as e:
        logger.error(f"Error getting job: {e}", exc_info=True)
        return jsonify(_format_response(
            success=False,
            status="error",
            code=500,
            error="Internal server error"
        )), 500


# ============================================================================
# PUT /api/v1/jobs/{job_id} - Update Job
# ============================================================================

@jobs_bp.route("/<job_id>", methods=["PUT"])
@validate_path_params(JobPathParams)
@validate_json_body(UpdateJobRequest)
def update_job(job_id):
    """
    Update job fields.
    
    Request body:
    {
        "priority": 7
    }
    
    Response:
    {
        "status": "success",
        "data": {...updated job...}
    }
    """
    try:
        logger.debug(f"Updating job: {job_id}")
        
        data = request.validated_data
        
        # Execute use case
        use_case = _resolve_use_case("update_job_use_case")
        job_dto = use_case.execute(job_id, priority=data.priority)
        
        logger.info(
            "Updated job successfully",
            extra={"job_id": job_id}
        )
        
        return jsonify(_format_response(
            success=True,
            data=job_dto.dict(),
            status="success",
            code=200
        )), 200
    
    except JobNotFoundError:
        logger.info(f"Job not found: {job_id}")
        return jsonify(_format_response(
            success=False,
            status="error",
            code=404,
            error=f"Job '{job_id}' not found"
        )), 404
    
    except (ValueError, InvalidJobStatusError) as e:
        logger.warning(f"Validation error in update_job: {e}")
        return jsonify(_format_response(
            success=False,
            status="error",
            code=400,
            error=str(e)
        )), 400
    
    except Exception as e:
        logger.error(f"Error updating job: {e}", exc_info=True)
        return jsonify(_format_response(
            success=False,
            status="error",
            code=500,
            error="Internal server error"
        )), 500


# ============================================================================
# DELETE /api/v1/jobs/{job_id} - Delete Job
# ============================================================================

@jobs_bp.route("/<job_id>", methods=["DELETE"])
@validate_path_params(JobPathParams)
def delete_job(job_id):
    """
    Delete a job.
    
    Users can only delete their own jobs.
    Admins can delete any job.
    
    Response:
    {
        "status": "success",
        "data": {
            "deleted": true
        }
    }
    """
    try:
        logger.debug(f"Deleting job: {job_id}")
        
        # Execute use case
        use_case = _resolve_use_case("delete_job_use_case")
        deleted = use_case.execute(
            job_id,
            user_id=_get_user_id(),
            is_admin=_get_is_admin(),
        )
        
        if not deleted:
            logger.info(f"Job not found: {job_id}")
            return jsonify(_format_response(
                success=False,
                status="error",
                code=404,
                error=f"Job '{job_id}' not found"
            )), 404
        
        logger.info(f"Deleted job successfully: {job_id}")
        
        return jsonify(_format_response(
            success=True,
            data={"deleted": True},
            status="success",
            code=200
        )), 200
    
    except PermissionError as e:
        logger.warning(f"Permission denied in delete_job: {e}")
        return jsonify(_format_response(
            success=False,
            status="error",
            code=403,
            error=str(e)
        )), 403
    
    except ValueError as e:
        logger.warning(f"Validation error in delete_job: {e}")
        return jsonify(_format_response(
            success=False,
            status="error",
            code=400,
            error=str(e)
        )), 400
    
    except Exception as e:
        logger.error(f"Error deleting job: {e}", exc_info=True)
        return jsonify(_format_response(
            success=False,
            status="error",
            code=500,
            error="Internal server error"
        )), 500


# ============================================================================
# POST /api/v1/jobs/{job_id}/cancel - Cancel Job
# ============================================================================

@jobs_bp.route("/<job_id>/cancel", methods=["POST"])
@validate_path_params(JobPathParams)
def cancel_job(job_id):
    """
    Cancel a pending or running job.
    
    Terminal states (completed, failed, cancelled) cannot be cancelled.
    
    Response:
    {
        "status": "success",
        "data": {...job with status=cancelled...}
    }
    """
    try:
        logger.debug(f"Cancelling job: {job_id}")
        
        # Execute use case
        use_case = _resolve_use_case("cancel_job_use_case")
        job_dto = use_case.execute(job_id)
        
        logger.info(
            "Cancelled job successfully",
            extra={"job_id": job_id}
        )
        
        return jsonify(_format_response(
            success=True,
            data=job_dto.dict(),
            status="success",
            code=200
        )), 200
    
    except JobNotFoundError:
        logger.info(f"Job not found: {job_id}")
        return jsonify(_format_response(
            success=False,
            status="error",
            code=404,
            error=f"Job '{job_id}' not found"
        )), 404
    
    except InvalidJobStatusError as e:
        logger.warning(f"Invalid status error in cancel_job: {e}")
        return jsonify(_format_response(
            success=False,
            status="error",
            code=400,
            error=str(e)
        )), 400
    
    except ValueError as e:
        logger.warning(f"Validation error in cancel_job: {e}")
        return jsonify(_format_response(
            success=False,
            status="error",
            code=400,
            error=str(e)
        )), 400
    
    except Exception as e:
        logger.error(f"Error cancelling job: {e}", exc_info=True)
        return jsonify(_format_response(
            success=False,
            status="error",
            code=500,
            error="Internal server error"
        )), 500
