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
    
    Orchestrates job creation and async submission:
    1. Validate input data
    2. Create domain entity
    3. Persist to repository
    4. Submit to AI Worker (async)
    5. Update job with AI Worker reference
    6. Publish domain events (optional)
    7. Return DTO to presentation layer
    
    This is an application layer component that coordinates
    domain logic without knowing about HTTP concerns.
    """
    
    def __init__(
        self,
        repository: IJobRepository,
        event_publisher: Optional[Any] = None,
        ai_worker_client: Optional[Any] = None,
    ):
        """Initialize use case
        
        Args:
            repository: Job repository implementation
            event_publisher: Optional event publisher for domain events
            ai_worker_client: Optional AI Worker client for job submission
        """
        
        self.repository = repository
        self.event_publisher = event_publisher
        self.ai_worker_client = ai_worker_client
    
    def execute(self, input_dto: CreateJobDTO) -> JobDTO:
        """Execute create job use case
        
        Args:
            input_dto: CreateJobDTO with job creation parameters
        
        Returns:
            JobDTO with created job data (with AI Worker job_id if submitted)
        
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
            
            logger.info("Job created in MongoDB", extra={
                "job_id": saved_job.id,
                "job_type": saved_job.job_type,
                "status": saved_job.status,
            })
            
            # Step 4: Submit to AI Worker (if client available)
            if self.ai_worker_client:
                try:
                    ai_job_id = self._submit_to_ai_worker(saved_job, input_dto)
                    
                    # Store AI Worker job_id reference
                    if ai_job_id:
                        saved_job.result = saved_job.result or {}
                        saved_job.result["ai_worker_job_id"] = ai_job_id
                        saved_job = self.repository.save(saved_job)
                        
                        logger.info("Job submitted to AI Worker", extra={
                            "job_id": saved_job.id,
                            "ai_job_id": ai_job_id,
                        })
                
                except Exception as e:
                    logger.warning(f"Failed to submit job to AI Worker: {e}", extra={
                        "job_id": saved_job.id,
                    })
                    # Don't fail the entire use case if AI Worker submission fails
                    # The job is already created in MongoDB
            
            # Step 5: Publish domain event (optional)
            if self.event_publisher:
                self._publish_job_created_event(saved_job)
            
            # Step 6: Convert to DTO and return
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
    
    def _submit_to_ai_worker(self, job: Job, input_dto: CreateJobDTO) -> Optional[str]:
        """Submit job to AI Worker for async execution
        
        Args:
            job: Created job entity
            input_dto: Original input DTO
            
        Returns:
            AI Worker job_id if successful, None otherwise
        """
        try:
            # Extract model info from input_data or use defaults
            model_id = job.input_data.get("model_id", "default")
            model_version = job.input_data.get("model_version", "1.0")
            
            logger.debug(f"Submitting job to AI Worker", extra={
                "job_id": job.id,
                "model_id": model_id,
                "model_version": model_version,
            })
            
            # Submit to AI Worker
            ai_job_id = self.ai_worker_client.submit_job(
                model_id=model_id,
                input_data=job.input_data,
                model_version=model_version
            )
            
            return ai_job_id
        
        except Exception as e:
            logger.error(f"AI Worker submission failed: {e}", exc_info=True, extra={
                "job_id": job.id,
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
                "created_at": job.created_at.isoformat().replace("+00:00", "Z"),
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
            created_at=job.created_at.isoformat().replace("+00:00", "Z"),
            completed_at=job.completed_at.isoformat().replace("+00:00", "Z") if job.completed_at else None,
            result=job.result,
            error=job.error,
        )
