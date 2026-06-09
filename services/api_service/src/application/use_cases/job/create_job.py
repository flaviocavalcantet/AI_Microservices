# Create Job use case

from typing import Optional, Dict, Any
from services.api_service.src.logger import get_logger
from services.api_service.src.application.dto import CreateJobDTO, JobDTO
from services.api_service.src.domain.entities.job import Job
from services.api_service.src.domain.repositories.job_repository import IJobRepository

logger = get_logger(__name__)


class CreateJobUseCase:
    """Create Job use case.

    Orchestrates job creation and async dispatch:
    1. Validate input data
    2. Create domain entity
    3. Persist to MongoDB with status ``pending``
    4. Dispatch to ``ai.default`` RabbitMQ queue via job_dispatcher
    5. Publish optional domain event
    6. Return DTO to presentation layer

    The ``job_dispatcher`` dependency accepts any object with a
    ``dispatch(job_id: str, job_payload: dict) -> None`` method.
    Pass ``None`` to skip dispatching (e.g. in tests).
    """

    def __init__(
        self,
        repository: IJobRepository,
        event_publisher: Optional[Any] = None,
        job_dispatcher: Optional[Any] = None,
    ):
        self.repository = repository
        self.event_publisher = event_publisher
        self.job_dispatcher = job_dispatcher

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, input_dto: CreateJobDTO) -> JobDTO:
        """Execute create job use case.

        Args:
            input_dto: CreateJobDTO with job creation parameters.

        Returns:
            JobDTO with created job data.

        Raises:
            ValueError: If input validation fails.
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
                raise ValueError("Job entity violates business invariants")

            # Step 3: Persist to MongoDB
            saved_job = self.repository.save(job)

            logger.info("Job created in MongoDB", extra={
                "job_id": saved_job.id,
                "job_type": saved_job.job_type,
                "status": saved_job.status,
            })

            # Step 4: Dispatch to RabbitMQ → celery-worker-ai
            if self.job_dispatcher:
                self._dispatch_to_queue(saved_job)

            # Step 5: Publish optional domain event
            if self.event_publisher:
                self._publish_job_created_event(saved_job)

            return self._map_to_dto(saved_job)

        except ValueError as e:
            logger.warning(f"Job creation validation failed: {e}", extra={
                "job_type": input_dto.job_type,
            })
            raise
        except Exception as e:
            logger.error(f"Job creation failed: {e}", exc_info=True, extra={
                "job_type": input_dto.job_type,
            })
            raise

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _dispatch_to_queue(self, job: Job) -> None:
        """Publish *job* to the RabbitMQ ``ai.default`` queue.

        Failure is logged but does **not** roll back the MongoDB record —
        the job remains in ``pending`` status and can be retried or
        inspected via the admin API.
        """
        try:
            job_payload = {
                "job_id": job.id,
                "job_type": job.job_type,
                "input_data": job.input_data,
                "user_id": job.user_id,
                "priority": job.priority,
                "timeout_seconds": job.timeout_seconds,
            }
            self.job_dispatcher.dispatch(job.id, job_payload)
            logger.info("Job dispatched to ai.default queue", extra={"job_id": job.id})
        except Exception as e:
            logger.error(
                "Failed to dispatch job to queue (job stays pending): %s",
                e,
                extra={"job_id": job.id},
            )
            # Best-effort: do not raise — job is already persisted.

    def _publish_job_created_event(self, job: Job) -> None:
        """Publish JobCreated domain event (optional, best-effort)."""
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
            logger.debug("JobCreated event published", extra={"job_id": job.id})
        except Exception as e:
            logger.error(f"Failed to publish JobCreated event: {e}", exc_info=True)

    @staticmethod
    def _map_to_dto(job: Job) -> JobDTO:
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
