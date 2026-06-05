"""
Job Manager for AI Worker

Manages the lifecycle of async jobs:
- Job submission and tracking
- State transitions (pending → running → completed)
- Result storage and retrieval
- Job cleanup
"""

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import json

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job status values"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Job representation"""
    id: str
    status: str  # JobStatus value
    payload: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    model_id: Optional[str] = None
    model_version: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary (serializable)"""
        return {
            "id": self.id,
            "status": self.status,
            "payload": self.payload,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "model_id": self.model_id,
            "model_version": self.model_version,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """Create job from dictionary"""
        # Convert ISO strings back to datetime
        for date_field in ["created_at", "started_at", "completed_at"]:
            if date_field in data and isinstance(data[date_field], str):
                data[date_field] = datetime.fromisoformat(data[date_field])
        
        return cls(**data)


class JobManager:
    """
    Manages job lifecycle.
    
    Uses in-memory storage with optional persistence layer.
    Future: Can be extended to use MongoDB or persistent queue.
    """
    
    def __init__(self, retention_days: int = 7, cleanup_interval_hours: int = 24):
        """
        Initialize Job Manager
        
        Args:
            retention_days: How many days to keep completed jobs
            cleanup_interval_hours: How often to cleanup old jobs
        """
        self.jobs: Dict[str, Job] = {}
        self.retention_days = retention_days
        self.cleanup_interval_hours = cleanup_interval_hours
        self.last_cleanup = datetime.now(timezone.utc)
        
        logger.info(f"JobManager initialized - retention: {retention_days} days, "
                   f"cleanup interval: {cleanup_interval_hours} hours")
    
    def create_job(self, payload: Dict[str, Any], model_id: Optional[str] = None,
                   model_version: Optional[str] = None) -> str:
        """
        Create a new job
        
        Args:
            payload: Job payload (model input, parameters, etc.)
            model_id: Model to execute
            model_version: Model version
            
        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            status=JobStatus.PENDING,
            payload=payload,
            model_id=model_id,
            model_version=model_version
        )
        
        self.jobs[job_id] = job
        logger.info(f"Job created: {job_id} (status: pending)")
        
        # Cleanup if needed
        self._cleanup_if_needed()
        
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve job by ID"""
        job = self.jobs.get(job_id)
        if job:
            logger.debug(f"Job retrieved: {job_id} (status: {job.status})")
        else:
            logger.warning(f"Job not found: {job_id}")
        return job
    
    def list_jobs(self, status: Optional[str] = None, limit: int = 100) -> List[Job]:
        """
        List jobs with optional filtering
        
        Args:
            status: Filter by status (e.g., "pending", "running")
            limit: Max jobs to return
            
        Returns:
            List of jobs
        """
        jobs = list(self.jobs.values())
        
        if status:
            jobs = [j for j in jobs if j.status == status]
        
        # Sort by created_at (newest first)
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        
        return jobs[:limit]
    
    def start_job(self, job_id: str) -> bool:
        """
        Mark job as running
        
        Args:
            job_id: Job ID
            
        Returns:
            True if successful, False if job not found or invalid state
        """
        job = self.get_job(job_id)
        if not job:
            logger.error(f"Cannot start job - not found: {job_id}")
            return False
        
        if job.status != JobStatus.PENDING:
            logger.error(f"Cannot start job {job_id} - invalid status: {job.status}")
            return False
        
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        return True
    
    def complete_job(self, job_id: str, result: Dict[str, Any]) -> bool:
        """
        Mark job as completed with result
        
        Args:
            job_id: Job ID
            result: Execution result
            
        Returns:
            True if successful
        """
        job = self.get_job(job_id)
        if not job:
            logger.error(f"Cannot complete job - not found: {job_id}")
            return False
        
        if job.status not in [JobStatus.RUNNING, JobStatus.PENDING]:
            logger.warning(f"Job {job_id} already in terminal state: {job.status}")
            return False
        
        job.status = JobStatus.COMPLETED
        job.result = result
        job.completed_at = datetime.now(timezone.utc)
        duration_ms = (job.completed_at - (job.started_at or job.created_at)).total_seconds() * 1000
        logger.info(f"Job completed: {job_id} (duration: {duration_ms:.0f}ms)")
        return True
    
    def fail_job(self, job_id: str, error: str) -> bool:
        """
        Mark job as failed
        
        Args:
            job_id: Job ID
            error: Error message
            
        Returns:
            True if successful
        """
        job = self.get_job(job_id)
        if not job:
            logger.error(f"Cannot fail job - not found: {job_id}")
            return False
        
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            logger.warning(f"Job {job_id} already in terminal state: {job.status}")
            return False
        
        job.status = JobStatus.FAILED
        job.error = error
        job.completed_at = datetime.now(timezone.utc)
        logger.error(f"Job failed: {job_id} - {error}")
        return True
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a pending/running job
        
        Args:
            job_id: Job ID
            
        Returns:
            True if successful
        """
        job = self.get_job(job_id)
        if not job:
            logger.error(f"Cannot cancel job - not found: {job_id}")
            return False
        
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            logger.warning(f"Cannot cancel job {job_id} - already in terminal state: {job.status}")
            return False
        
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc)
        logger.info(f"Job cancelled: {job_id}")
        return True
    
    def update_job_status(self, job_id: str, status: str, 
                         result: Optional[Dict[str, Any]] = None,
                         error: Optional[str] = None) -> bool:
        """
        Update job status and optionally result/error
        
        Args:
            job_id: Job ID
            status: New status (JobStatus value)
            result: Execution result (if completed)
            error: Error message (if failed)
            
        Returns:
            True if successful
        """
        job = self.get_job(job_id)
        if not job:
            logger.error(f"Cannot update job - not found: {job_id}")
            return False
        
        # Validate status transition
        valid_next_states = {
            JobStatus.PENDING: [JobStatus.RUNNING, JobStatus.CANCELLED],
            JobStatus.RUNNING: [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED],
            JobStatus.COMPLETED: [],
            JobStatus.FAILED: [],
            JobStatus.CANCELLED: []
        }
        
        if status not in valid_next_states.get(job.status, []):
            logger.error(f"Invalid state transition for job {job_id}: "
                        f"{job.status} -> {status}")
            return False
        
        # Update job
        old_status = job.status
        job.status = status
        
        if status == JobStatus.RUNNING and not job.started_at:
            job.started_at = datetime.now(timezone.utc)
        
        if status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            job.completed_at = datetime.now(timezone.utc)
        
        if result is not None:
            job.result = result
        
        if error is not None:
            job.error = error
        
        logger.info(f"Job status updated: {job_id} ({old_status} -> {status})")
        return True
    
    def _cleanup_if_needed(self):
        """Cleanup old completed jobs"""
        now = datetime.now(timezone.utc)
        if (now - self.last_cleanup).total_seconds() < (self.cleanup_interval_hours * 3600):
            return
        
        self.cleanup_old_jobs(retention_days=self.retention_days)
        self.last_cleanup = now
    
    def cleanup_old_jobs(self, retention_days: int = 7) -> int:
        """
        Remove completed/failed jobs older than retention period
        
        Args:
            retention_days: How many days to keep
            
        Returns:
            Number of jobs cleaned up
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        jobs_to_delete = [
            job_id for job_id, job in self.jobs.items()
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]
            and job.completed_at
            and job.completed_at < cutoff_date
        ]
        
        for job_id in jobs_to_delete:
            del self.jobs[job_id]
        
        if jobs_to_delete:
            logger.info(f"Cleaned up {len(jobs_to_delete)} old jobs")
        
        return len(jobs_to_delete)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get job queue statistics"""
        stats = {
            "total_jobs": len(self.jobs),
            "by_status": {}
        }
        
        for status in JobStatus:
            count = sum(1 for j in self.jobs.values() if j.status == status)
            if count > 0:
                stats["by_status"][status] = count
        
        # Running jobs count
        running = self.list_jobs(status=JobStatus.RUNNING)
        stats["active_jobs"] = len(running)
        
        # Average execution time for completed jobs
        completed = self.list_jobs(status=JobStatus.COMPLETED)
        if completed:
            avg_time = sum(
                (j.completed_at - j.started_at).total_seconds() * 1000
                for j in completed if j.started_at and j.completed_at
            ) / len(completed)
            stats["avg_execution_time_ms"] = avg_time
        
        return stats
