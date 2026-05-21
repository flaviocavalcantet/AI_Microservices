"""
Delete Job Use Case

Deletes a job (typically only soft-delete for audit trail).
"""

import logging

from services.api_service.src.domain.entities.job import Job
from services.api_service.src.domain.repositories.job_repository import IJobRepository
from services.api_service.src.application.exceptions import JobNotFoundError


logger = logging.getLogger(__name__)


class DeleteJobUseCase:
    """
    Deletes a job.
    
    In production, this should be soft-delete to maintain audit trail.
    Only jobs can delete their own jobs, or admins can delete any.
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
    
    def execute(self, job_id: str, user_id: str, is_admin: bool = False) -> bool:
        """
        Delete job.
        
        Args:
            job_id: ID of job to delete
            user_id: User requesting deletion (for permission check)
            is_admin: Whether user is admin (admins can delete any job)
        
        Returns:
            True if deleted, False if not found
        
        Raises:
            ValueError: If parameters invalid
            PermissionError: If user not authorized to delete
        """
        try:
            if not job_id or not isinstance(job_id, str):
                raise ValueError("job_id must be a non-empty string")
            if not user_id or not isinstance(user_id, str):
                raise ValueError("user_id must be a non-empty string")
            
            logger.debug(f"Deleting job: job_id={job_id}, user_id={user_id}")
            
            # Check existence
            job = self.repository.find_by_id(job_id)
            if not job:
                logger.info(f"Job not found: job_id={job_id}")
                return False
            
            # Check permissions (own job or admin)
            if not is_admin and job.user_id != user_id:
                logger.warning(
                    f"Permission denied: user_id={user_id} cannot delete "
                    f"job_id={job_id} owned by {job.user_id}"
                )
                raise PermissionError(
                    "You can only delete your own jobs. Contact admin for assistance."
                )
            
            # Delete from repository
            deleted = self.repository.delete(job_id)
            
            if deleted:
                # Publish event if publisher available
                if self.event_publisher:
                    self._publish_job_deleted_event(job, user_id)
                
                logger.info(
                    f"Deleted job: job_id={job_id}, owner={job.user_id}, "
                    f"deleted_by={user_id}"
                )
            
            return deleted
        
        except (ValueError, PermissionError):
            raise
        except Exception as e:
            logger.error(f"Delete job failed: {e}", exc_info=True)
            raise
    
    def _publish_job_deleted_event(self, job: Job, deleted_by: str):
        """Publish JobDeleted domain event."""
        try:
            self.event_publisher.publish({
                "event_type": "JobDeleted",
                "job_id": job.id,
                "user_id": job.user_id,
                "deleted_by": deleted_by,
                "status": job.status,
            })
            logger.debug(f"Published JobDeleted event: job_id={job.id}")
        except Exception as e:
            logger.warning(f"Failed to publish JobDeleted event: {e}")
