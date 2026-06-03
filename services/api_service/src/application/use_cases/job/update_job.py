"""
Update Job Use Case

Updates job fields (currently priority).
"""

import logging
from typing import Optional

from services.api_service.src.domain.entities.job import Job
from services.api_service.src.domain.repositories.job_repository import IJobRepository
from services.api_service.src.application.dto.job_dto import JobDTO
from services.api_service.src.application.exceptions import JobNotFoundError


logger = logging.getLogger(__name__)


class UpdateJobUseCase:
    """
    Updates job fields.
    
    Currently supports updating:
    - priority: Job priority (1-10)
    
    Does not support updating:
    - status: Use specific transitions instead (start, complete, fail, cancel)
    - job_type: Immutable after creation
    - input_data: Immutable after creation
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
    
    def execute(self, job_id: str, priority: Optional[int] = None,
                status: Optional[str] = None, result: Optional[dict] = None,
                error: Optional[str] = None) -> JobDTO:
        """
        Update job.
        
        Args:
            job_id: ID of job to update
            priority: New priority (1-10)
            status: New job status (for AI Worker status sync)
            result: Execution result (for AI Worker result sync)
            error: Error message (for AI Worker error sync)
        
        Returns:
            Updated JobDTO
        
        Raises:
            JobNotFoundError: If job not found
            ValueError: If parameters invalid
        """
        try:
            if not job_id or not isinstance(job_id, str):
                raise ValueError("job_id must be a non-empty string")
            
            logger.debug(f"Updating job: job_id={job_id}, priority={priority}, status={status}")
            
            # Get current job
            job = self.repository.find_by_id(job_id)
            if not job:
                logger.info(f"Job not found: job_id={job_id}")
                raise JobNotFoundError(job_id)
            
            # Apply updates
            if priority is not None:
                if priority < 1 or priority > 10:
                    raise ValueError("priority must be between 1 and 10")
                job.priority = priority
            
            if status is not None:
                job.status = status
            
            if result is not None:
                job.result = result
            
            if error is not None:
                job.error = error
            
            # Validate business rules
            if not job.is_valid():
                raise ValueError("Job invariants violated after update")
            
            # Persist
            updated_job = self.repository.save(job)
            
            # Publish event if publisher available
            if self.event_publisher:
                self._publish_job_updated_event(updated_job)
            
            logger.info(f"Updated job: job_id={job_id}")
            
            return self._map_to_dto(updated_job)
        
        except (JobNotFoundError, ValueError):
            raise
        except Exception as e:
            logger.error(f"Update job failed: {e}", exc_info=True)
            raise
    
    def _publish_job_updated_event(self, job: Job):
        """Publish JobUpdated domain event."""
        try:
            self.event_publisher.publish({
                "event_type": "JobUpdated",
                "job_id": job.id,
                "user_id": job.user_id,
                "status": job.status,
                "priority": job.priority,
                "updated_at": job.completed_at.isoformat() if job.completed_at else None,
            })
            logger.debug(f"Published JobUpdated event: job_id={job.id}")
        except Exception as e:
            logger.warning(f"Failed to publish JobUpdated event: {e}")
    
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
