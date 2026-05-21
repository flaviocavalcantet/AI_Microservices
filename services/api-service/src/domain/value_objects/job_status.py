# Value objects for domain layer

# Job Status value object
class JobStatus:
    """Job status enumeration (value object)"""
    
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    
    VALID_STATUSES = {PENDING, RUNNING, COMPLETED, FAILED, CANCELLED}
    
    TERMINAL_STATUSES = {COMPLETED, FAILED, CANCELLED}
    
    @classmethod
    def is_valid(cls, status: str) -> bool:
        """Check if status is valid"""
        return status in cls.VALID_STATUSES
    
    @classmethod
    def is_terminal(cls, status: str) -> bool:
        """Check if status is terminal (no further changes possible)"""
        return status in cls.TERMINAL_STATUSES
    
    @classmethod
    def can_transition(cls, from_status: str, to_status: str) -> bool:
        """Check if transition is allowed"""
        # Terminal statuses cannot transition
        if cls.is_terminal(from_status):
            return False
        
        # Valid transitions
        valid_transitions = {
            cls.PENDING: {cls.RUNNING, cls.CANCELLED},
            cls.RUNNING: {cls.COMPLETED, cls.FAILED, cls.CANCELLED},
        }
        
        return to_status in valid_transitions.get(from_status, set())


class Priority:
    """Priority value object (1-10)"""
    
    MIN = 1
    MAX = 10
    
    def __init__(self, value: int):
        if not (self.MIN <= value <= self.MAX):
            raise ValueError(f"Priority must be between {self.MIN} and {self.MAX}")
        self.value = value
    
    def __int__(self):
        return self.value
    
    def __eq__(self, other):
        if isinstance(other, Priority):
            return self.value == other.value
        return self.value == other
    
    def __lt__(self, other):
        if isinstance(other, Priority):
            return self.value < other.value
        return self.value < other
