"""
Cancel Job Use Case

Cancels a pending or running job.
"""

import logging

from services.api_service.src.domain.entities.job import Job
from services.api_service.src.domain.repositories.job_repository import IJobRepository
from services.api_service.src.application.dto.job_dto import JobDTO
from services.api_service.src.application.exceptions import (
    JobNotFoundError,
    InvalidJobStatusError,
)


logger = logging.getLogger(__name__)


class CancelJobUseCase:
    """
    Cancels a job that is pending or running.
    
    Terminal states (completed, failed, cancelled) cannot be cancelled.
    """
    
    def __init__(self, repository: IJobRepository, event_publisher=None):
        """
        Initialize with repository and optional event publisher.
        
        Args:
            repository: IJobRepository implementation
            event_publisher: Optional event publisher for domain events
        """
        self.repository = repository
        self.event_publisher = event_publisher
    
    def execute(self, job_id: str) -> JobDTO:
        """
        Cancel job.
        
        Args:
            job_id: ID of job to cancel
        
        Returns:
            Cancelled JobDTO
        
        Raises:
            JobNotFoundError: If job not found
            InvalidJobStatusError: If job cannot be cancelled
            ValueError: If job_id invalid
        """
        try:
            if not job_id or not isinstance(job_id, str):
                raise ValueError("job_id must be a non-empty string")
            
            logger.debug(f"Cancelling job: job_id={job_id}")
            
            # Get job
            job = self.repository.find_by_id(job_id)
            if not job:
                logger.info(f"Job not found: job_id={job_id}")
                raise JobNotFoundError(job_id)
            
            # Check if cancellable (must be pending or running)
            if job.status not in ["pending", "running"]:
                raise InvalidJobStatusError(
                    f"Cannot cancel job in '{job.status}' state. "
                    f"Only 'pending' and 'running' jobs can be cancelled."
                )
            
            # Cancel job
            job.cancel()
            
            # Persist
            cancelled_job = self.repository.save(job)
            
            # Publish event if publisher available
            if self.event_publisher:
                self._publish_job_cancelled_event(cancelled_job)
            
            logger.info(f"Cancelled job: job_id={job_id}, prev_status={job.status}")
            
            return self._map_to_dto(cancelled_job)
        
        except (JobNotFoundError, InvalidJobStatusError):
            raise
        except ValueError as e:
            logger.warning(f"Validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Cancel job failed: {e}", exc_info=True)
            raise
    
    def _publish_job_cancelled_event(self, job: Job):
        """Publish JobCancelled domain event."""
        try:
            self.event_publisher.publish({
                "event_type": "JobCancelled",
                "job_id": job.id,
                "user_id": job.user_id,
                "cancelled_at": job.completed_at.isoformat() if job.completed_at else None,
            })
            logger.debug(f"Published JobCancelled event: job_id={job.id}")
        except Exception as e:
            logger.warning(f"Failed to publish JobCancelled event: {e}")
    
    def _map_to_dto(self, job: Job) -> JobDTO:
        """Convert Job entity to JobDTO."""
        return JobDTO(
            id=job.id,
            user_id=job.user_id,
            job_type=job.job_type,
            status=job.status,
            priority=job.priority,
            created_at=job.created_at.isoformat() + "Z" if job.created_at else None,
            started_at=job.started_at.isoformat() + "Z" if job.started_at else None,
            completed_at=job.completed_at.isoformat() + "Z" if job.completed_at else None,
            result=job.result,
            error=job.error,
            input_data=job.input_data,
            timeout_seconds=job.timeout_seconds,
        )
