# Application exceptions

class ApplicationException(Exception):
    """Base application exception"""
    pass


class JobNotFoundError(ApplicationException):
    """Job not found"""
    pass


class InvalidJobStatusError(ApplicationException):
    """Invalid job status for operation"""
    pass


class JobAlreadyExistsError(ApplicationException):
    """Job already exists"""
    pass


class InsufficientPermissionsError(ApplicationException):
    """User doesn't have permission"""
    pass
