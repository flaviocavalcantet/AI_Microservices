"""
Get Job Use Case

Retrieves a single job by ID.
"""

import logging
from typing import Optional

from services.api_service.src.domain.entities.job import Job
from services.api_service.src.domain.repositories.job_repository import IJobRepository
from services.api_service.src.application.dto.job_dto import JobDTO
from services.api_service.src.application.exceptions import JobNotFoundError


logger = logging.getLogger(__name__)


class GetJobUseCase:
    """
    Retrieves a single job by ID.
    
    Raises NotFoundError if job doesn't exist.
    """
    
    def __init__(self, repository: IJobRepository):
        """
        Initialize with repository.
        
        Args:
            repository: IJobRepository implementation
        """
        self.repository = repository
    
    def execute(self, job_id: str) -> JobDTO:
        """
        Get job by ID.
        
        Args:
            job_id: ID of job to retrieve
        
        Returns:
            JobDTO
        
        Raises:
            JobNotFoundError: If job not found
            ValueError: If job_id is invalid
        """
        try:
            if not job_id or not isinstance(job_id, str):
                raise ValueError("job_id must be a non-empty string")
            
            logger.debug(f"Getting job: job_id={job_id}")
            
            # Query repository
            job = self.repository.find_by_id(job_id)
            
            if not job:
                logger.info(f"Job not found: job_id={job_id}")
                raise JobNotFoundError(job_id)
            
            # Convert to DTO
            job_dto = self._map_to_dto(job)
            
            logger.info(f"Retrieved job: job_id={job_id}, status={job.status}")
            
            return job_dto
        
        except JobNotFoundError:
            raise
        except ValueError as e:
            logger.warning(f"Validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Get job failed: {e}", exc_info=True)
            raise
    
    def _map_to_dto(self, job: Job) -> JobDTO:
        """Convert Job entity to JobDTO."""
        return JobDTO(
            id=job.id,
            user_id=job.user_id,
            job_type=job.job_type,
            status=job.status,
            priority=job.priority,
            created_at=job.created_at.isoformat().replace("+00:00", "Z") if job.created_at else None,
            started_at=job.started_at.isoformat().replace("+00:00", "Z") if job.started_at else None,
            completed_at=job.completed_at.isoformat().replace("+00:00", "Z") if job.completed_at else None,
            result=job.result,
            error=job.error,
            input_data=job.input_data,
            timeout_seconds=job.timeout_seconds,
        )
