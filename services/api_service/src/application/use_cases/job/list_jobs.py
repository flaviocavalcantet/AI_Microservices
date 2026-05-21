"""
List Jobs Use Case

Retrieves jobs with filtering, sorting, and pagination.
"""

from typing import List, Tuple, Optional
import logging

from services.api_service.src.domain.entities.job import Job
from services.api_service.src.domain.repositories.job_repository import IJobRepository
from services.api_service.src.application.dto.job_dto import JobDTO


logger = logging.getLogger(__name__)


class ListJobsUseCase:
    """
    Lists jobs with optional filtering, sorting, and pagination.
    
    Filters:
    - user_id: Filter by job owner
    - status: Filter by job status
    - job_type: Filter by job type
    
    Sorting:
    - sort_by: Field to sort by (created_at, status, priority)
    - sort_order: asc or desc
    
    Pagination:
    - limit: Number of results per page
    - offset: Starting position
    """
    
    def __init__(self, repository: IJobRepository):
        """
        Initialize with repository.
        
        Args:
            repository: IJobRepository implementation
        """
        self.repository = repository
    
    def execute(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[JobDTO], int]:
        """
        List jobs with filters and pagination.
        
        Args:
            user_id: Optional filter by user
            status: Optional filter by status
            job_type: Optional filter by job type
            limit: Results per page (default 10, max 100)
            offset: Starting position (default 0)
            sort_by: Field to sort by (created_at, status, priority)
            sort_order: Sort direction (asc, desc)
        
        Returns:
            Tuple of (list of JobDTOs, total count)
        
        Raises:
            ValueError: If parameters invalid
        """
        try:
            # Validate parameters
            if limit < 1 or limit > 100:
                raise ValueError("limit must be between 1 and 100")
            if offset < 0:
                raise ValueError("offset must be >= 0")
            
            valid_sort_by = ["created_at", "status", "priority"]
            if sort_by not in valid_sort_by:
                raise ValueError(f"sort_by must be one of {valid_sort_by}")
            
            valid_sort_order = ["asc", "desc"]
            if sort_order not in valid_sort_order:
                raise ValueError(f"sort_order must be one of {valid_sort_order}")
            
            logger.debug(
                f"Listing jobs: user_id={user_id}, status={status}, "
                f"limit={limit}, offset={offset}"
            )
            
            # Query repository
            jobs, total = self.repository.find_all(
                user_id=user_id,
                status=status,
                job_type=job_type,
                limit=limit,
                offset=offset,
                sort_by=sort_by,
                sort_order=sort_order,
            )
            
            # Convert to DTOs
            job_dtos = [self._map_to_dto(job) for job in jobs]
            
            logger.info(
                f"Listed {len(job_dtos)} jobs (total: {total}), "
                f"user_id={user_id}, status={status}"
            )
            
            return job_dtos, total
        
        except ValueError as e:
            logger.warning(f"Validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"List jobs failed: {e}", exc_info=True)
            raise
    
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
