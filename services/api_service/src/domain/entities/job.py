# Job domain entity

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import uuid4
from services.api_service.src.domain.value_objects.job_status import JobStatus, Priority


@dataclass
class Job:
    """Job domain entity - represents a background job for AI processing
    
    This is a pure domain entity with no framework dependencies.
    It encapsulates business logic and validates invariants.
    
    Attributes:
        id: Unique identifier
        user_id: User who created the job
        job_type: Type of job (model_training, inference, etc.)
        status: Current status (pending, running, completed, failed, cancelled)
        priority: Priority level (1-10)
        input_data: Input parameters for the job
        result: Job result (when completed)
        error: Error message (if failed)
        created_at: When job was created
        started_at: When job started running
        completed_at: When job finished
        timeout_seconds: Maximum execution time
    """
    
    id: str
    user_id: Optional[str]
    job_type: str
    status: str
    priority: int
    input_data: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    timeout_seconds: Optional[int] = None
    
    @classmethod
    def create(
        cls,
        job_type: str,
        input_data: Dict[str, Any],
        user_id: Optional[str] = None,
        priority: int = 5,
        timeout_seconds: Optional[int] = None,
    ) -> "Job":
        """Factory method to create new job entity
        
        Args:
            job_type: Type of job
            input_data: Input parameters
            user_id: User creating the job
            priority: Priority level (1-10, default 5)
            timeout_seconds: Maximum execution time
        
        Returns:
            New Job entity
        
        Raises:
            ValueError: If job_type or priority invalid
        """
        
        # Validate job_type is not empty
        if not job_type or not job_type.strip():
            raise ValueError("job_type cannot be empty")
        
        # Validate priority is in valid range
        try:
            priority_vo = Priority(priority)
        except ValueError as e:
            raise ValueError(f"Invalid priority: {e}")
        
        # Create new job
        job = cls(
            id=str(uuid4()),
            user_id=user_id,
            job_type=job_type.strip(),
            status=JobStatus.PENDING,
            priority=priority_vo.value,
            input_data=input_data or {},
            result=None,
            error=None,
            created_at=datetime.utcnow(),
            started_at=None,
            completed_at=None,
            timeout_seconds=timeout_seconds,
        )
        
        return job
    
    def start(self) -> None:
        """Transition job to RUNNING status
        
        Raises:
            ValueError: If job cannot transition to RUNNING
        """
        
        if not JobStatus.can_transition(self.status, JobStatus.RUNNING):
            raise ValueError(
                f"Cannot transition from {self.status} to {JobStatus.RUNNING}"
            )
        
        self.status = JobStatus.RUNNING
        self.started_at = datetime.utcnow()
    
    def complete(self, result: Dict[str, Any]) -> None:
        """Mark job as completed with result
        
        Args:
            result: Job result data
        
        Raises:
            ValueError: If job is not in RUNNING status
        """
        
        if not JobStatus.can_transition(self.status, JobStatus.COMPLETED):
            raise ValueError(
                f"Cannot transition from {self.status} to {JobStatus.COMPLETED}"
            )
        
        self.status = JobStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.utcnow()
        self.error = None
    
    def fail(self, error_message: str) -> None:
        """Mark job as failed with error
        
        Args:
            error_message: Description of the error
        
        Raises:
            ValueError: If job cannot fail from current status
        """
        
        if not JobStatus.can_transition(self.status, JobStatus.FAILED):
            raise ValueError(
                f"Cannot transition from {self.status} to {JobStatus.FAILED}"
            )
        
        self.status = JobStatus.FAILED
        self.error = error_message
        self.result = None
        self.completed_at = datetime.utcnow()
    
    def cancel(self) -> None:
        """Cancel the job
        
        Raises:
            ValueError: If job cannot be cancelled
        """
        
        if not JobStatus.can_transition(self.status, JobStatus.CANCELLED):
            raise ValueError(
                f"Cannot transition from {self.status} to {JobStatus.CANCELLED}"
            )
        
        self.status = JobStatus.CANCELLED
        self.completed_at = datetime.utcnow()
    
    def is_valid(self) -> bool:
        """Check if job satisfies business rule invariants
        
        Returns:
            True if job is in valid state
        """
        
        # Check required fields
        if not self.id or not self.job_type:
            return False
        
        # Check status is valid
        if not JobStatus.is_valid(self.status):
            return False
        
        # Check priority is in valid range
        if not (Priority.MIN <= self.priority <= Priority.MAX):
            return False
        
        # Check timestamps are consistent
        if self.started_at and self.created_at:
            if self.started_at < self.created_at:
                return False
        
        if self.completed_at:
            if self.created_at and self.completed_at < self.created_at:
                return False
            if self.started_at and self.completed_at < self.started_at:
                return False
        
        # Check terminal state consistency
        if JobStatus.is_terminal(self.status):
            if not self.completed_at:
                return False
        else:
            if self.status == JobStatus.RUNNING:
                if not self.started_at:
                    return False
        
        # Check result/error consistency
        if self.status == JobStatus.COMPLETED:
            if self.error is not None:
                return False
        
        if self.status == JobStatus.FAILED:
            if not self.error:
                return False
        
        return True
    
    def get_elapsed_seconds(self) -> Optional[float]:
        """Get elapsed time in seconds
        
        Returns:
            Elapsed seconds, or None if not started
        """
        
        if not self.started_at:
            return None
        
        end_time = self.completed_at or datetime.utcnow()
        elapsed = (end_time - self.started_at).total_seconds()
        
        return elapsed
    
    def is_timed_out(self) -> bool:
        """Check if job has exceeded timeout
        
        Returns:
            True if job exceeded timeout duration
        """
        
        if not self.timeout_seconds or not self.started_at:
            return False
        
        elapsed = self.get_elapsed_seconds()
        if elapsed is None:
            return False
        
        return elapsed > self.timeout_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation
        
        Returns:
            Dictionary with all fields
        """
        
        return {
            "id": self.id,
            "user_id": self.user_id,
            "job_type": self.job_type,
            "status": self.status,
            "priority": self.priority,
            "input_data": self.input_data,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
            "started_at": self.started_at.isoformat() + "Z" if self.started_at else None,
            "completed_at": self.completed_at.isoformat() + "Z" if self.completed_at else None,
            "timeout_seconds": self.timeout_seconds,
        }
    
    def __repr__(self) -> str:
        """String representation"""
        return (
            f"Job(id={self.id}, job_type={self.job_type}, "
            f"status={self.status}, priority={self.priority})"
        )
