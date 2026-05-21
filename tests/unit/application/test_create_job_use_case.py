# Unit tests for CreateJobUseCase

import pytest
from unittest.mock import Mock, MagicMock
from services.api_service.src.application.use_cases.job.create_job import CreateJobUseCase
from services.api_service.src.application.dto import CreateJobDTO
from services.api_service.src.domain.entities.job import Job


class MockRepository:
    """Mock job repository for testing"""
    
    def __init__(self):
        self.saved_jobs = {}
    
    def save(self, job: Job) -> Job:
        """Mock save implementation"""
        self.saved_jobs[job.id] = job
        return job
    
    def find_by_id(self, job_id: str):
        return self.saved_jobs.get(job_id)


class TestCreateJobUseCase:
    """Test CreateJobUseCase"""
    
    def test_execute_creates_job_successfully(self):
        """Test successful job creation"""
        
        # Arrange
        repository = MockRepository()
        use_case = CreateJobUseCase(repository)
        
        input_dto = CreateJobDTO(
            job_type="model_training",
            input_data={"model": "bert", "lr": 0.001},
            priority=7,
            user_id="user-123",
        )
        
        # Act
        result = use_case.execute(input_dto)
        
        # Assert
        assert result is not None
        assert result.id is not None
        assert result.job_type == "model_training"
        assert result.status == "pending"
        assert result.priority == 7
        assert result.user_id == "user-123"
    
    def test_execute_persists_to_repository(self):
        """Test job is saved to repository"""
        
        # Arrange
        repository = MockRepository()
        use_case = CreateJobUseCase(repository)
        
        input_dto = CreateJobDTO(
            job_type="inference",
            input_data={"image": "base64..."},
            priority=5,
            user_id="user-123",
        )
        
        # Act
        result = use_case.execute(input_dto)
        
        # Assert
        assert repository.find_by_id(result.id) is not None
    
    def test_execute_with_invalid_job_type_fails(self):
        """Test creation fails with invalid job_type"""
        
        # Arrange
        repository = MockRepository()
        use_case = CreateJobUseCase(repository)
        
        # Act & Assert
        # Pydantic validates job_type cannot be empty
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            CreateJobDTO(
                job_type="",  # Invalid
                input_data={},
                user_id="user-123",
            )
    
    def test_execute_with_invalid_priority_fails(self):
        """Test creation fails with invalid priority"""
        
        # Arrange
        repository = MockRepository()
        use_case = CreateJobUseCase(repository)
        
        # Act & Assert
        # Pydantic validates priority must be <= 10
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            CreateJobDTO(
                job_type="training",
                input_data={},
                priority=15,  # Invalid
                user_id="user-123",
            )
    
    def test_execute_publishes_event_if_publisher_configured(self):
        """Test job creation event is published"""
        
        # Arrange
        repository = MockRepository()
        event_publisher = Mock()
        use_case = CreateJobUseCase(repository, event_publisher)
        
        input_dto = CreateJobDTO(
            job_type="training",
            input_data={"model": "bert"},
            user_id="user-123",
        )
        
        # Act
        result = use_case.execute(input_dto)
        
        # Assert
        event_publisher.publish.assert_called_once()
        call_args = event_publisher.publish.call_args
        event_data = call_args[0][0]
        assert event_data["event_type"] == "JobCreated"
        assert event_data["job_id"] == result.id
        assert event_data["user_id"] == "user-123"
    
    def test_execute_without_event_publisher(self):
        """Test job creation works without event publisher"""
        
        # Arrange
        repository = MockRepository()
        use_case = CreateJobUseCase(repository)  # No event publisher
        
        input_dto = CreateJobDTO(
            job_type="training",
            input_data={},
            user_id="user-123",
        )
        
        # Act & Assert - should not raise
        result = use_case.execute(input_dto)
        assert result is not None
    
    def test_execute_dto_to_entity_mapping(self):
        """Test DTO is correctly mapped to domain entity"""
        
        # Arrange
        repository = MockRepository()
        use_case = CreateJobUseCase(repository)
        
        input_dto = CreateJobDTO(
            job_type="evaluation",
            input_data={"dataset": "test"},
            user_id="user-456",
            priority=3,
            timeout_seconds=7200,
        )
        
        # Act
        result = use_case.execute(input_dto)
        
        # Assert
        assert result.job_type == "evaluation"
        assert result.user_id == "user-456"
        assert result.priority == 3
    
    def test_execute_returns_dto_not_entity(self):
        """Test execute returns DTO, not entity"""
        
        # Arrange
        repository = MockRepository()
        use_case = CreateJobUseCase(repository)
        
        input_dto = CreateJobDTO(
            job_type="training",
            input_data={},
            user_id="user-123",
        )
        
        # Act
        result = use_case.execute(input_dto)
        
        # Assert
        from services.api_service.src.application.dto import JobDTO
        assert isinstance(result, JobDTO)
    
    def test_execute_sets_created_at_timestamp(self):
        """Test job gets created_at timestamp"""
        
        # Arrange
        from datetime import datetime, timezone
        repository = MockRepository()
        use_case = CreateJobUseCase(repository)
        
        # Use UTC time for comparison
        before = datetime.now(timezone.utc).replace(microsecond=0)
        
        input_dto = CreateJobDTO(
            job_type="training",
            input_data={},
            user_id="user-123",
        )
        
        # Act
        result = use_case.execute(input_dto)
        
        after = datetime.now(timezone.utc)
        
        # Assert
        # Parse the ISO-8601 timestamp
        created_at_str = result.created_at.replace('Z', '+00:00')
        created_at = datetime.fromisoformat(created_at_str)
        
        # Check the timestamp is between before and after
        assert before <= created_at <= after


class TestCreateJobUseCaseIntegration:
    """Integration tests with real domain layer"""
    
    def test_full_workflow_create_start_complete(self):
        """Test full job workflow"""
        
        # Create job
        repository = MockRepository()
        create_use_case = CreateJobUseCase(repository)
        
        input_dto = CreateJobDTO(
            job_type="training",
            input_data={"model": "bert"},
            priority=5,
            user_id="user-123",
        )
        
        job_dto = create_use_case.execute(input_dto)
        
        # Retrieve job from repository
        job = repository.find_by_id(job_dto.id)
        
        # Verify job entity
        assert job.status == "pending"
        
        # Start job
        job.start()
        assert job.status == "running"
        
        # Complete job
        job.complete({"accuracy": 0.95})
        assert job.status == "completed"
        assert job.result == {"accuracy": 0.95}
    
    def test_full_workflow_create_fail(self):
        """Test job creation and failure workflow"""
        
        repository = MockRepository()
        use_case = CreateJobUseCase(repository)
        
        input_dto = CreateJobDTO(
            job_type="training",
            input_data={},
            user_id="user-123",
        )
        
        result = use_case.execute(input_dto)
        job = repository.find_by_id(result.id)
        
        # Start and fail
        job.start()
        job.fail("Out of memory")
        
        assert job.status == "failed"
        assert job.error == "Out of memory"
