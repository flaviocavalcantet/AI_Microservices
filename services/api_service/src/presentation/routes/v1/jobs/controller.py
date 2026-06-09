"""
Jobs API Blueprint Controller

Implements all job-related endpoints:
- POST   /api/v1/jobs              - Create job          (any authenticated user)
- GET    /api/v1/jobs              - List jobs           (own jobs; admin sees all)
- GET    /api/v1/jobs/{id}         - Get job             (owner or admin)
- PUT    /api/v1/jobs/{id}         - Update job          (owner or admin)
- DELETE /api/v1/jobs/{id}         - Delete job          (owner or admin)
- POST   /api/v1/jobs/{id}/cancel  - Cancel job          (owner or admin)

Auth contract
-------------
Every route is protected with @require_auth — requests without a valid JWT
are rejected 401 unconditionally, regardless of the JWT_AUTH_REQUIRED config
flag.  JWT_AUTH_REQUIRED (and JWT_AUTH_ENABLED=False) remain available as
escape hatches for local development and automated tests, but production
routes do not depend on them.

Role contract
-------------
- "user"  : may create, read, update, cancel, and delete **their own** jobs.
- "admin" : may perform all operations on **any** job, and may list any
            user's jobs by passing a ?user_id= query parameter.

The @require_auth decorator is applied first (innermost); additional ownership
checks are performed inside each handler using _assert_owner_or_admin().
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, current_app, g, jsonify, request

from services.api_service.src.application.dto.job_dto import CreateJobDTO
from services.api_service.src.application.exceptions import (
    InvalidJobStatusError,
    JobNotFoundError,
)
from services.api_service.src.application.use_cases.job import (
    CancelJobUseCase,
    CreateJobUseCase,
    DeleteJobUseCase,
    GetJobUseCase,
    ListJobsUseCase,
    UpdateJobUseCase,
)
from services.api_service.src.container import resolve_from_context
from services.api_service.src.errors import ForbiddenError, UnauthorizedError
from services.api_service.src.logger import get_logger
from services.api_service.src.presentation.middleware.jwt_middleware import get_require_auth
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

jobs_bp = Blueprint(
    name="jobs",
    import_name=__name__,
    url_prefix="/api/v1/jobs",
)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _require_auth(fn):
    """Per-route auth guard — delegates to the decorator registered by
    register_jwt_auth() at app startup.  Falls back to a hard 401 if the
    extension is somehow absent (defensive, should never happen in prod)."""
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        decorator = current_app.extensions.get("require_auth")
        if decorator is None:
            # Middleware was not registered — fail closed.
            raise UnauthorizedError("Authentication middleware not configured")
        return decorator(fn)(*args, **kwargs)

    return wrapper


def _get_caller_user_id() -> str:
    """Return the authenticated user's ID from the JWT context."""
    return getattr(g, "user_id", None) or "anonymous"


def _is_admin() -> bool:
    """Return True if the authenticated user holds the 'admin' role."""
    return "admin" in set(getattr(g, "roles", []) or [])


def _assert_owner_or_admin(job_user_id: str) -> None:
    """Raise ForbiddenError unless the caller owns the job or is an admin."""
    if not _is_admin() and _get_caller_user_id() != job_user_id:
        raise ForbiddenError("You do not have permission to access this job")


def _format_response(success: bool, data=None, error=None, status="success", code=200):
    payload = {
        "status": status,
        "code": code,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if data is not None:
        payload["data"] = data
    if error is not None:
        payload["error"] = error
    return payload


# ---------------------------------------------------------------------------
# POST /api/v1/jobs — Create job
# ---------------------------------------------------------------------------

@jobs_bp.route("", methods=["POST"])
@_require_auth
@validate_json_body(CreateJobRequest)
def create_job():
    """
    Create a new job.

    Requires: authenticated user (any role).

    Request body:
        job_type        string  required
        input_data      dict    required
        priority        int     optional (1-10, default 5)
        timeout_seconds int     optional (1-86400, default 3600)
    """
    try:
        data = request.validated_data
        create_dto = CreateJobDTO(
            job_type=data.job_type,
            input_data=data.input_data,
            priority=data.priority,
            timeout_seconds=data.timeout_seconds,
            user_id=_get_caller_user_id(),
        )
        use_case: CreateJobUseCase = resolve_from_context("create_job_use_case")
        job_dto = use_case.execute(create_dto)

        logger.info(
            "Job created",
            extra={"job_id": job_dto.id, "user_id": job_dto.user_id, "job_type": job_dto.job_type},
        )
        return jsonify(_format_response(success=True, data=job_dto.dict(), status="success", code=201)), 201

    except ValueError as exc:
        logger.warning(f"Validation error in create_job: {exc}")
        return jsonify(_format_response(success=False, status="error", code=400, error=str(exc))), 400
    except Exception as exc:
        logger.error(f"Error creating job: {exc}", exc_info=True)
        return jsonify(_format_response(success=False, status="error", code=500, error="Internal server error")), 500


# ---------------------------------------------------------------------------
# GET /api/v1/jobs — List jobs
# ---------------------------------------------------------------------------

@jobs_bp.route("", methods=["GET"])
@_require_auth
@validate_query_params(ListJobsQuery)
def list_jobs():
    """
    List jobs with optional filtering and pagination.

    Requires: authenticated user (any role).
    Scoping:  non-admins are always scoped to their own user_id, regardless
              of the ?user_id= query parameter.  Admins may pass any user_id
              (or omit it to list all jobs).
    """
    try:
        query = request.validated_query
        caller_id = _get_caller_user_id()

        # Enforce scoping: non-admins can only see their own jobs.
        if _is_admin():
            effective_user_id = query.user_id  # None = all jobs
        else:
            if query.user_id and query.user_id != caller_id:
                raise ForbiddenError("You can only list your own jobs")
            effective_user_id = caller_id

        use_case: ListJobsUseCase = resolve_from_context("list_jobs_use_case")
        job_dtos, total = use_case.execute(
            user_id=effective_user_id,
            status=query.status,
            job_type=query.job_type,
            limit=query.limit,
            offset=query.offset,
            sort_by=query.sort_by,
            sort_order=query.sort_order,
        )

        logger.info(
            "Listed jobs",
            extra={"count": len(job_dtos), "total": total, "user_id": effective_user_id},
        )
        return jsonify(_format_response(
            success=True,
            data={"jobs": [j.dict() for j in job_dtos], "total": total, "limit": query.limit, "offset": query.offset},
            status="success",
            code=200,
        )), 200

    except ForbiddenError:
        raise
    except ValueError as exc:
        logger.warning(f"Validation error in list_jobs: {exc}")
        return jsonify(_format_response(success=False, status="error", code=400, error=str(exc))), 400
    except Exception as exc:
        logger.error(f"Error listing jobs: {exc}", exc_info=True)
        return jsonify(_format_response(success=False, status="error", code=500, error="Internal server error")), 500


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/<job_id> — Get job
# ---------------------------------------------------------------------------

@jobs_bp.route("/<job_id>", methods=["GET"])
@_require_auth
@validate_path_params(JobPathParams)
def get_job(job_id):
    """
    Get a single job by ID.

    Requires: authenticated user; must be the job owner or an admin.
    """
    try:
        use_case: GetJobUseCase = resolve_from_context("get_job_use_case")
        job_dto = use_case.execute(job_id)

        _assert_owner_or_admin(job_dto.user_id)

        logger.info("Retrieved job", extra={"job_id": job_id, "status": job_dto.status})
        return jsonify(_format_response(success=True, data=job_dto.dict(), status="success", code=200)), 200

    except JobNotFoundError:
        return jsonify(_format_response(success=False, status="error", code=404, error=f"Job '{job_id}' not found")), 404
    except ForbiddenError:
        raise
    except ValueError as exc:
        return jsonify(_format_response(success=False, status="error", code=400, error=str(exc))), 400
    except Exception as exc:
        logger.error(f"Error getting job: {exc}", exc_info=True)
        return jsonify(_format_response(success=False, status="error", code=500, error="Internal server error")), 500


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/<job_id>/status — Poll job status
# ---------------------------------------------------------------------------

@jobs_bp.route("/<job_id>/status", methods=["GET"])
@_require_auth
@validate_path_params(JobPathParams)
def poll_job_status(job_id):
    """
    Return the current status of a job from MongoDB.

    ``celery-worker-ai`` writes the terminal status (completed / failed)
    directly back to the api-service MongoDB record, so this endpoint
    just reads from the database — no HTTP fan-out to ai-worker required.

    Requires: authenticated user; must be the job owner or an admin.

    Returns:
    {
        "job_id":  "<uuid>",
        "status":  "pending|running|completed|failed|cancelled",
        "result":  {...} | null,
        "error":   null | "<message>"
    }
    """
    try:
        use_case: GetJobUseCase = resolve_from_context("get_job_use_case")
        job_dto = use_case.execute(job_id)

        _assert_owner_or_admin(job_dto.user_id)

        logger.info(
            "Polled job status",
            extra={"job_id": job_id, "status": job_dto.status},
        )
        return jsonify(_format_response(
            success=True,
            data={
                "job_id": job_dto.id,
                "status": job_dto.status,
                "result": job_dto.result,
                "error": job_dto.error,
            },
            status="success",
            code=200,
        )), 200

    except JobNotFoundError:
        return jsonify(_format_response(
            success=False, status="error", code=404,
            error=f"Job '{job_id}' not found",
        )), 404
    except ForbiddenError:
        raise
    except ValueError as exc:
        return jsonify(_format_response(
            success=False, status="error", code=400, error=str(exc),
        )), 400
    except Exception as exc:
        logger.error(f"Error polling job status: {exc}", exc_info=True)
        return jsonify(_format_response(
            success=False, status="error", code=500,
            error="Internal server error",
        )), 500


# ---------------------------------------------------------------------------
# PUT /api/v1/jobs/<job_id> — Update job
# ---------------------------------------------------------------------------

@jobs_bp.route("/<job_id>", methods=["PUT"])
@_require_auth
@validate_path_params(JobPathParams)
@validate_json_body(UpdateJobRequest)
def update_job(job_id):
    """
    Update job fields (currently: priority).

    Requires: authenticated user; must be the job owner or an admin.
    """
    try:
        # Fetch first so we can check ownership before mutating.
        get_uc: GetJobUseCase = resolve_from_context("get_job_use_case")
        existing = get_uc.execute(job_id)
        _assert_owner_or_admin(existing.user_id)

        data = request.validated_data
        update_uc: UpdateJobUseCase = resolve_from_context("update_job_use_case")
        job_dto = update_uc.execute(job_id, priority=data.priority)

        logger.info("Updated job", extra={"job_id": job_id})
        return jsonify(_format_response(success=True, data=job_dto.dict(), status="success", code=200)), 200

    except JobNotFoundError:
        return jsonify(_format_response(success=False, status="error", code=404, error=f"Job '{job_id}' not found")), 404
    except ForbiddenError:
        raise
    except (ValueError, InvalidJobStatusError) as exc:
        return jsonify(_format_response(success=False, status="error", code=400, error=str(exc))), 400
    except Exception as exc:
        logger.error(f"Error updating job: {exc}", exc_info=True)
        return jsonify(_format_response(success=False, status="error", code=500, error="Internal server error")), 500


# ---------------------------------------------------------------------------
# DELETE /api/v1/jobs/<job_id> — Delete job
# ---------------------------------------------------------------------------

@jobs_bp.route("/<job_id>", methods=["DELETE"])
@_require_auth
@validate_path_params(JobPathParams)
def delete_job(job_id):
    """
    Delete a job.

    Requires: authenticated user; must be the job owner or an admin.
    Ownership is enforced both in this controller and inside DeleteJobUseCase
    (defence-in-depth).
    """
    try:
        use_case: DeleteJobUseCase = resolve_from_context("delete_job_use_case")
        deleted = use_case.execute(
            job_id,
            user_id=_get_caller_user_id(),
            is_admin=_is_admin(),
        )

        if not deleted:
            return jsonify(_format_response(success=False, status="error", code=404, error=f"Job '{job_id}' not found")), 404

        logger.info("Deleted job", extra={"job_id": job_id})
        return jsonify(_format_response(success=True, data={"deleted": True}, status="success", code=200)), 200

    except PermissionError as exc:
        raise ForbiddenError(str(exc))
    except ForbiddenError:
        raise
    except ValueError as exc:
        return jsonify(_format_response(success=False, status="error", code=400, error=str(exc))), 400
    except Exception as exc:
        logger.error(f"Error deleting job: {exc}", exc_info=True)
        return jsonify(_format_response(success=False, status="error", code=500, error="Internal server error")), 500


# ---------------------------------------------------------------------------
# POST /api/v1/jobs/<job_id>/cancel — Cancel job
# ---------------------------------------------------------------------------

@jobs_bp.route("/<job_id>/cancel", methods=["POST"])
@_require_auth
@validate_path_params(JobPathParams)
def cancel_job(job_id):
    """
    Cancel a pending or running job.

    Requires: authenticated user; must be the job owner or an admin.
    Terminal states (completed, failed, cancelled) cannot be cancelled.
    """
    try:
        use_case: CancelJobUseCase = resolve_from_context("cancel_job_use_case")
        job_dto = use_case.execute(
            job_id,
            user_id=_get_caller_user_id(),
            is_admin=_is_admin(),
        )

        logger.info("Cancelled job", extra={"job_id": job_id})
        return jsonify(_format_response(success=True, data=job_dto.dict(), status="success", code=200)), 200

    except JobNotFoundError:
        return jsonify(_format_response(success=False, status="error", code=404, error=f"Job '{job_id}' not found")), 404
    except PermissionError as exc:
        raise ForbiddenError(str(exc))
    except ForbiddenError:
        raise
    except InvalidJobStatusError as exc:
        return jsonify(_format_response(success=False, status="error", code=400, error=str(exc))), 400
    except ValueError as exc:
        return jsonify(_format_response(success=False, status="error", code=400, error=str(exc))), 400
    except Exception as exc:
        logger.error(f"Error cancelling job: {exc}", exc_info=True)
        return jsonify(_format_response(success=False, status="error", code=500, error="Internal server error")), 500
