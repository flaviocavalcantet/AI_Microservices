# Job repository interface (contract for data access)

from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from services.api_service.src.domain.entities.job import Job


class IJobRepository(ABC):
    """Repository interface for Job entity
    
    Defines the contract for accessing and persisting Job data.
    Implementations can use MongoDB, PostgreSQL, or any other storage.
    
    This interface is framework-independent and part of the domain layer.
    """
    
    @abstractmethod
    def save(self, job: Job) -> Job:
        """Save job (insert or update)
        
        Args:
            job: Job entity to save
        
        Returns:
            Saved job with ID populated
        
        Raises:
            RepositoryError: If save operation fails
        """
        pass
    
    @abstractmethod
    def find_by_id(self, job_id: str) -> Optional[Job]:
        """Find job by ID
        
        Args:
            job_id: Job ID
        
        Returns:
            Job entity or None if not found
        
        Raises:
            RepositoryError: If query fails
        """
        pass
    
    @abstractmethod
    def find_all(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[Job], int]:
        """Find jobs with optional filters
        
        Args:
            user_id: Filter by user
            status: Filter by status (pending, running, completed, failed, cancelled)
            job_type: Filter by job type
            limit: Items per page
            offset: Starting position
            sort_by: Field to sort by
            sort_order: Sort order (asc, desc)
        
        Returns:
            Tuple of (jobs list, total count)
        
        Raises:
            RepositoryError: If query fails
        """
        pass
    
    @abstractmethod
    def find_by_status(
        self,
        status: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Job], int]:
        """Find jobs by status (commonly used query)
        
        Args:
            status: Job status
            limit: Items per page
            offset: Starting position
        
        Returns:
            Tuple of (jobs list, total count)
        """
        pass
    
    @abstractmethod
    def find_by_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Job], int]:
        """Find jobs for specific user
        
        Args:
            user_id: User ID
            limit: Items per page
            offset: Starting position
        
        Returns:
            Tuple of (jobs list, total count)
        """
        pass
    
    @abstractmethod
    def update_status(self, job_id: str, status: str) -> Optional[Job]:
        """Update only job status (optimization for status changes)
        
        Args:
            job_id: Job ID
            status: New status
        
        Returns:
            Updated job or None if not found
        """
        pass
    
    @abstractmethod
    def delete(self, job_id: str) -> bool:
        """Delete job
        
        Args:
            job_id: Job ID
        
        Returns:
            True if deleted, False if not found
        """
        pass
    
    @abstractmethod
    def exists(self, job_id: str) -> bool:
        """Check if job exists
        
        Args:
            job_id: Job ID
        
        Returns:
            True if exists
        """
        pass
    
    @abstractmethod
    def count(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int:
        """Count jobs with optional filters
        
        Args:
            user_id: Optional user filter
            status: Optional status filter
        
        Returns:
            Count of matching jobs
        """
        pass
