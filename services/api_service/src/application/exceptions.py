"""
Application Layer Exceptions

Custom exceptions for the application layer.
Used for domain-specific error handling.
"""


class ApplicationException(Exception):
    """Base exception for all application layer errors"""
    pass


class JobNotFoundError(ApplicationException):
    """Raised when a job is not found in the repository"""
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        super().__init__(f"Job not found: {job_id}")


class InvalidJobStatusError(ApplicationException):
    """Raised when attempting an invalid job status transition"""
    
    def __init__(self, message: str):
        super().__init__(message)


class JobAlreadyExistsError(ApplicationException):
    """Raised when attempting to create a duplicate job"""
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        super().__init__(f"Job already exists: {job_id}")


class InsufficientPermissionsError(ApplicationException):
    """Raised when user lacks permissions for operation"""
    
    def __init__(self, message: str):
        super().__init__(message)
