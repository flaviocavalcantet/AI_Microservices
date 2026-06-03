"""
AI Worker Job Routes

HTTP endpoints for submitting and tracking async jobs
"""

import logging
from flask import Blueprint, request, jsonify
from typing import Tuple, Dict, Any

logger = logging.getLogger(__name__)


def create_jobs_blueprint(container) -> Blueprint:
    """
    Create jobs blueprint with endpoints
    
    Args:
        container: Service container with registered dependencies
        
    Returns:
        Flask Blueprint
    """
    jobs_bp = Blueprint('jobs', __name__, url_prefix='/api/v1/ai/jobs')
    
    @jobs_bp.route('', methods=['POST'])
    def submit_job() -> Tuple[Dict[str, Any], int]:
        """
        Submit a job for async execution
        
        Expected JSON:
        {
            "model_id": "sentiment",
            "model_version": "1.0",
            "input_data": {
                "input": [1.0, 2.0, 3.0, ...]
            }
        }
        
        Returns:
        {
            "job_id": "uuid",
            "status": "pending",
            "created_at": "2026-05-29T10:00:00"
        }
        """
        try:
            data = request.get_json()
            
            if not data:
                logger.warning("Empty request body")
                return {"error": "Request body required"}, 400
            
            model_id = data.get('model_id')
            model_version = data.get('model_version', '1.0')
            input_data = data.get('input_data', {})
            
            if not model_id:
                return {"error": "model_id required"}, 400
            
            if not input_data:
                logger.warning(f"Empty input_data for model {model_id}")
                # Allow empty input for some models
            
            # Get dependencies from container
            job_manager = container.resolve("job_manager")
            
            # Create job (doesn't execute yet)
            job_id = job_manager.create_job(
                payload=input_data,
                model_id=model_id,
                model_version=model_version
            )
            
            job = job_manager.get_job(job_id)
            
            return {
                "job_id": job_id,
                "status": job.status,
                "created_at": job.created_at.isoformat(),
                "message": "Job submitted successfully. Poll GET /jobs/{job_id} for results."
            }, 202  # 202 Accepted
        
        except Exception as e:
            logger.error(f"Error submitting job: {e}")
            return {"error": str(e)}, 500
    
    @jobs_bp.route('/<job_id>', methods=['GET'])
    def get_job(job_id: str) -> Tuple[Dict[str, Any], int]:
        """
        Get full job details (status, input, result, error)
        
        Returns:
        {
            "id": "uuid",
            "status": "running",
            "model_id": "sentiment",
            "model_version": "1.0",
            "payload": {...},
            "result": null,
            "error": null,
            "created_at": "...",
            "started_at": "...",
            "completed_at": null
        }
        """
        try:
            job_manager = container.resolve("job_manager")
            job = job_manager.get_job(job_id)
            
            if not job:
                return {"error": f"Job not found: {job_id}"}, 404
            
            return job.to_dict(), 200
        
        except Exception as e:
            logger.error(f"Error retrieving job {job_id}: {e}")
            return {"error": str(e)}, 500
    
    @jobs_bp.route('/<job_id>/status', methods=['GET'])
    def get_job_status(job_id: str) -> Tuple[Dict[str, Any], int]:
        """
        Get job status only (lightweight)
        
        Returns:
        {
            "job_id": "uuid",
            "status": "completed",
            "result": {...} (if completed),
            "error": null
        }
        """
        try:
            job_manager = container.resolve("job_manager")
            job = job_manager.get_job(job_id)
            
            if not job:
                return {"error": f"Job not found: {job_id}"}, 404
            
            response = {
                "job_id": job.id,
                "status": job.status,
            }
            
            if job.result is not None:
                response["result"] = job.result
            
            if job.error is not None:
                response["error"] = job.error
            
            return response, 200
        
        except Exception as e:
            logger.error(f"Error retrieving job status {job_id}: {e}")
            return {"error": str(e)}, 500
    
    @jobs_bp.route('', methods=['GET'])
    def list_jobs() -> Tuple[Dict[str, Any], int]:
        """
        List jobs with optional filtering
        
        Query parameters:
        - status: Filter by status (pending, running, completed, failed, cancelled)
        - limit: Max jobs to return (default 100)
        
        Returns:
        {
            "jobs": [
                {
                    "id": "uuid",
                    "status": "completed",
                    "created_at": "...",
                    ...
                },
                ...
            ],
            "total": 50
        }
        """
        try:
            status = request.args.get('status')
            limit = int(request.args.get('limit', 100))
            
            job_manager = container.resolve("job_manager")
            jobs = job_manager.list_jobs(status=status, limit=limit)
            
            return {
                "jobs": [j.to_dict() for j in jobs],
                "total": len(jobs)
            }, 200
        
        except ValueError as e:
            return {"error": f"Invalid query parameter: {e}"}, 400
        except Exception as e:
            logger.error(f"Error listing jobs: {e}")
            return {"error": str(e)}, 500
    
    @jobs_bp.route('/<job_id>/cancel', methods=['POST'])
    def cancel_job(job_id: str) -> Tuple[Dict[str, Any], int]:
        """
        Cancel a pending or running job
        
        Returns:
        {
            "job_id": "uuid",
            "status": "cancelled"
        }
        """
        try:
            job_manager = container.resolve("job_manager")
            job = job_manager.get_job(job_id)
            
            if not job:
                return {"error": f"Job not found: {job_id}"}, 404
            
            if not job_manager.cancel_job(job_id):
                return {
                    "error": f"Cannot cancel job in state: {job.status}"
                }, 409  # 409 Conflict
            
            job = job_manager.get_job(job_id)
            return {
                "job_id": job.id,
                "status": job.status,
                "cancelled_at": job.completed_at.isoformat() if job.completed_at else None
            }, 200
        
        except Exception as e:
            logger.error(f"Error cancelling job {job_id}: {e}")
            return {"error": str(e)}, 500
    
    @jobs_bp.route('/stats', methods=['GET'])
    def get_stats() -> Tuple[Dict[str, Any], int]:
        """
        Get job queue statistics
        
        Returns:
        {
            "total_jobs": 100,
            "active_jobs": 5,
            "by_status": {
                "pending": 20,
                "running": 5,
                "completed": 70,
                "failed": 5
            },
            "avg_execution_time_ms": 1234.5
        }
        """
        try:
            job_manager = container.resolve("job_manager")
            stats = job_manager.get_statistics()
            return stats, 200
        
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {"error": str(e)}, 500
    
    return jobs_bp
