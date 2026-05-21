"""
Job Status Value Objects

Immutable value objects for job status and priority.
Encapsulates validation and business rules.
"""


class JobStatus:
    """
    Immutable job status value object.
    
    Valid statuses: pending, running, completed, failed, cancelled
    
    Supports state machine transitions with validation.
    """
    
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    
    VALID_STATUSES = [PENDING, RUNNING, COMPLETED, FAILED, CANCELLED]
    
    # Valid state transitions
    TRANSITIONS = {
        PENDING: [RUNNING, CANCELLED],
        RUNNING: [COMPLETED, FAILED, CANCELLED],
        COMPLETED: [],  # Terminal
        FAILED: [],     # Terminal
        CANCELLED: [],  # Terminal
    }
    
    @staticmethod
    def is_valid(status: str) -> bool:
        """
        Check if status is valid.
        
        Args:
            status: Status string to validate
        
        Returns:
            True if valid, False otherwise
        """
        return status in JobStatus.VALID_STATUSES
    
    @staticmethod
    def is_terminal(status: str) -> bool:
        """
        Check if status is terminal (no further transitions allowed).
        
        Args:
            status: Status to check
        
        Returns:
            True if terminal state
        """
        return status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]
    
    @staticmethod
    def can_transition(from_status: str, to_status: str) -> bool:
        """
        Check if transition from one status to another is allowed.
        
        Args:
            from_status: Current status
            to_status: Target status
        
        Returns:
            True if transition allowed
        """
        if not JobStatus.is_valid(from_status):
            return False
        if not JobStatus.is_valid(to_status):
            return False
        
        return to_status in JobStatus.TRANSITIONS.get(from_status, [])


class Priority:
    """
    Immutable priority value object.
    
    Valid range: 1-10
    Lower numbers = higher priority
    
    Example:
        >>> priority = Priority(5)
        >>> priority.value
        5
        >>> Priority(11)  # Raises ValueError
    """
    
    MIN = 1
    MAX = 10
    DEFAULT = 5
    
    def __init__(self, value: int):
        """
        Initialize priority value object.
        
        Args:
            value: Priority integer (1-10)
        
        Raises:
            ValueError: If value not in valid range
            TypeError: If value is not an integer
        """
        if not isinstance(value, int):
            raise ValueError(f"Priority must be an integer, got {type(value).__name__}")
        
        if value < self.MIN or value > self.MAX:
            raise ValueError(f"Priority must be between {self.MIN} and {self.MAX}, got {value}")
        
        self._value = value
    
    @property
    def value(self) -> int:
        """Get the priority value"""
        return self._value
    
    def __eq__(self, other):
        """Compare priorities"""
        if isinstance(other, Priority):
            return self._value == other._value
        return self._value == other
    
    def __lt__(self, other):
        """Less than comparison (lower number = higher priority)"""
        if isinstance(other, Priority):
            return self._value < other._value
        return self._value < other
    
    def __le__(self, other):
        """Less than or equal comparison"""
        if isinstance(other, Priority):
            return self._value <= other._value
        return self._value <= other
    
    def __gt__(self, other):
        """Greater than comparison"""
        if isinstance(other, Priority):
            return self._value > other._value
        return self._value > other
    
    def __ge__(self, other):
        """Greater than or equal comparison"""
        if isinstance(other, Priority):
            return self._value >= other._value
        return self._value >= other
    
    def __repr__(self) -> str:
        """String representation"""
        return f"Priority({self._value})"
    
    def __str__(self) -> str:
        """String conversion"""
        return str(self._value)
    
    @staticmethod
    def is_valid(priority: int) -> bool:
        """
        Check if priority is valid.
        
        Args:
            priority: Priority value (integer)
        
        Returns:
            True if valid
        """
        if not isinstance(priority, int):
            return False
        return Priority.MIN <= priority <= Priority.MAX
