# Create Job use case

from typing import Optional, Dict, Any
from services.api_service.src.logger import get_logger
from services.api_service.src.application.dto import CreateJobDTO, JobDTO
from services.api_service.src.application.exceptions import InvalidJobStatusError
from services.api_service.src.domain.entities.job import Job
from services.api_service.src.domain.repositories.job_repository import IJobRepository

logger = get_logger(__name__)


class CreateJobUseCase:
    """Create Job use case
    
    Orchestrates job creation:
    1. Validate input data
    2. Create domain entity
    3. Persist to repository
    4. Publish domain events (optional)
    5. Return DTO to presentation layer
    
    This is an application layer component that coordinates
    domain logic without knowing about HTTP concerns.
    """
    
    def __init__(
        self,
        repository: IJobRepository,
        event_publisher: Optional[Any] = None,
    ):
        """Initialize use case
        
        Args:
            repository: Job repository implementation
            event_publisher: Optional event publisher for domain events
        """
        
        self.repository = repository
        self.event_publisher = event_publisher
    
    def execute(self, input_dto: CreateJobDTO) -> JobDTO:
        """Execute create job use case
        
        Args:
            input_dto: CreateJobDTO with job creation parameters
        
        Returns:
            JobDTO with created job data
        
        Raises:
            ValueError: If input validation fails
            RepositoryError: If persistence fails
        """
        
        logger.info("Creating job", extra={
            "job_type": input_dto.job_type,
            "priority": input_dto.priority,
        })
        
        try:
            # Step 1: Create domain entity (includes validation)
            job = Job.create(
                job_type=input_dto.job_type,
                input_data=input_dto.input_data,
                user_id=input_dto.user_id,
                priority=input_dto.priority,
                timeout_seconds=input_dto.timeout_seconds,
            )
            
            # Step 2: Validate entity invariants
            if not job.is_valid():
                logger.error("Created job violates invariants", extra={
                    "job_id": job.id,
                    "status": job.status,
                })
                raise ValueError("Job entity violates business invariants")
            
            # Step 3: Persist to repository
            saved_job = self.repository.save(job)
            
            logger.info("Job created successfully", extra={
                "job_id": saved_job.id,
                "job_type": saved_job.job_type,
                "status": saved_job.status,
            })
            
            # Step 4: Publish domain event (optional)
            if self.event_publisher:
                self._publish_job_created_event(saved_job)
            
            # Step 5: Convert to DTO and return
            return self._map_to_dto(saved_job)
        
        except ValueError as e:
            logger.warning(f"Job creation validation failed: {e}", extra={
                "job_type": input_dto.job_type,
                "error": str(e),
            })
            raise
        
        except Exception as e:
            logger.error(f"Job creation failed: {e}", exc_info=True, extra={
                "job_type": input_dto.job_type,
            })
            raise
    
    def _publish_job_created_event(self, job: Job) -> None:
        """Publish JobCreated domain event
        
        Args:
            job: Created job entity
        """
        
        try:
            event_data = {
                "event_type": "JobCreated",
                "event_version": "1.0",
                "job_id": job.id,
                "user_id": job.user_id,
                "job_type": job.job_type,
                "priority": job.priority,
                "created_at": job.created_at.isoformat() + "Z",
                "input_data": job.input_data,
            }
            
            self.event_publisher.publish(event_data)
            
            logger.debug("JobCreated event published", extra={
                "job_id": job.id,
                "event_type": "JobCreated",
            })
        
        except Exception as e:
            logger.error(f"Failed to publish JobCreated event: {e}", exc_info=True)
            # Don't raise - event publishing is optional
    
    @staticmethod
    def _map_to_dto(job: Job) -> JobDTO:
        """Map domain entity to DTO
        
        Args:
            job: Job entity
        
        Returns:
            JobDTO
        """
        
        return JobDTO(
            id=job.id,
            user_id=job.user_id,
            job_type=job.job_type,
            status=job.status,
            priority=job.priority,
            created_at=job.created_at.isoformat() + "Z",
            completed_at=job.completed_at.isoformat() + "Z" if job.completed_at else None,
            result=job.result,
            error=job.error,
        )
