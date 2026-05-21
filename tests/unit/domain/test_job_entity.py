# Unit tests for Job domain entity

import pytest
from datetime import datetime, timedelta
from services.api_service.src.domain.entities.job import Job
from services.api_service.src.domain.value_objects.job_status import JobStatus, Priority


class TestJobCreation:
    """Test Job entity creation"""
    
    def test_create_valid_job(self):
        """Test creating a valid job"""
        
        job = Job.create(
            job_type="model_training",
            input_data={"model": "bert"},
            user_id="user-123",
            priority=5,
        )
        
        assert job.id is not None
        assert job.job_type == "model_training"
        assert job.status == JobStatus.PENDING
        assert job.priority == 5
        assert job.user_id == "user-123"
        assert job.input_data == {"model": "bert"}
        assert job.created_at is not None
        assert job.started_at is None
        assert job.completed_at is None
        assert job.is_valid()
    
    def test_create_job_with_default_priority(self):
        """Test job creation with default priority"""
        
        job = Job.create(
            job_type="inference",
            input_data={},
        )
        
        assert job.priority == 5  # default
    
    def test_create_job_invalid_job_type_empty(self):
        """Test creating job with empty job_type fails"""
        
        with pytest.raises(ValueError):
            Job.create(
                job_type="",
                input_data={},
            )
    
    def test_create_job_invalid_priority(self):
        """Test creating job with invalid priority fails"""
        
        with pytest.raises(ValueError):
            Job.create(
                job_type="training",
                input_data={},
                priority=11,  # Out of range
            )
    
    def test_create_job_with_timeout(self):
        """Test job creation with timeout"""
        
        job = Job.create(
            job_type="training",
            input_data={},
            timeout_seconds=3600,
        )
        
        assert job.timeout_seconds == 3600


class TestJobTransitions:
    """Test Job status transitions"""
    
    def test_transition_pending_to_running(self):
        """Test transitioning from pending to running"""
        
        job = Job.create("training", {})
        assert job.status == JobStatus.PENDING
        
        job.start()
        
        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None
    
    def test_transition_running_to_completed(self):
        """Test transitioning from running to completed"""
        
        job = Job.create("training", {})
        job.start()
        
        job.complete({"accuracy": 0.95})
        
        assert job.status == JobStatus.COMPLETED
        assert job.completed_at is not None
        assert job.result == {"accuracy": 0.95}
        assert job.error is None
    
    def test_transition_running_to_failed(self):
        """Test transitioning from running to failed"""
        
        job = Job.create("training", {})
        job.start()
        
        job.fail("Out of memory")
        
        assert job.status == JobStatus.FAILED
        assert job.completed_at is not None
        assert job.error == "Out of memory"
        assert job.result is None
    
    def test_transition_pending_to_cancelled(self):
        """Test cancelling pending job"""
        
        job = Job.create("training", {})
        
        job.cancel()
        
        assert job.status == JobStatus.CANCELLED
        assert job.completed_at is not None
    
    def test_invalid_transition_completed_to_running(self):
        """Test that completed jobs cannot transition"""
        
        job = Job.create("training", {})
        job.start()
        job.complete({"result": "ok"})
        
        with pytest.raises(ValueError):
            job.start()
    
    def test_invalid_transition_failed_to_running(self):
        """Test that failed jobs cannot transition"""
        
        job = Job.create("training", {})
        job.start()
        job.fail("Error")
        
        with pytest.raises(ValueError):
            job.complete({"result": "ok"})


class TestJobValidation:
    """Test Job validation"""
    
    def test_valid_job_passes_validation(self):
        """Test that properly created job is valid"""
        
        job = Job.create("training", {})
        assert job.is_valid()
    
    def test_job_with_invalid_timestamps_fails_validation(self):
        """Test job with invalid timestamps is invalid"""
        
        job = Job.create("training", {})
        job.start()
        
        # Manually set invalid state
        job.completed_at = job.created_at - timedelta(seconds=1)
        
        assert not job.is_valid()
    
    def test_completed_job_with_error_fails_validation(self):
        """Test completed job cannot have error"""
        
        job = Job.create("training", {})
        job.start()
        job.complete({"result": "ok"})
        
        # Manually set invalid state
        job.error = "Some error"
        
        assert not job.is_valid()
    
    def test_failed_job_without_error_fails_validation(self):
        """Test failed job must have error message"""
        
        job = Job.create("training", {})
        job.start()
        job.fail("Error")
        
        # Manually set invalid state
        job.error = None
        
        assert not job.is_valid()


class TestJobElapsedTime:
    """Test Job elapsed time calculation"""
    
    def test_get_elapsed_seconds_not_started(self):
        """Test elapsed time is None for not-started job"""
        
        job = Job.create("training", {})
        
        assert job.get_elapsed_seconds() is None
    
    def test_get_elapsed_seconds_running(self):
        """Test elapsed time for running job"""
        
        job = Job.create("training", {})
        job.start()
        
        import time
        time.sleep(0.1)  # Sleep 100ms
        
        elapsed = job.get_elapsed_seconds()
        assert elapsed is not None
        assert elapsed >= 0.1
    
    def test_is_not_timed_out(self):
        """Test job is not timed out"""
        
        job = Job.create("training", {}, timeout_seconds=1)
        job.start()
        
        assert not job.is_timed_out()
    
    def test_is_timed_out(self):
        """Test job is timed out"""
        
        job = Job.create("training", {}, timeout_seconds=0.1)
        job.start()
        
        import time
        time.sleep(0.2)  # Sleep longer than timeout
        
        assert job.is_timed_out()
    
    def test_no_timeout_check_when_not_set(self):
        """Test timeout check when timeout not set"""
        
        job = Job.create("training", {})  # No timeout
        job.start()
        
        assert not job.is_timed_out()


class TestJobConversion:
    """Test Job entity conversions"""
    
    def test_to_dict(self):
        """Test converting job to dictionary"""
        
        job = Job.create(
            job_type="training",
            input_data={"model": "bert"},
            user_id="user-123",
            priority=7,
        )
        
        job_dict = job.to_dict()
        
        assert job_dict["id"] == job.id
        assert job_dict["job_type"] == "training"
        assert job_dict["status"] == JobStatus.PENDING
        assert job_dict["priority"] == 7
        assert job_dict["user_id"] == "user-123"
        assert job_dict["input_data"] == {"model": "bert"}
        assert "created_at" in job_dict
    
    def test_to_dict_with_result(self):
        """Test dict conversion includes result"""
        
        job = Job.create("training", {})
        job.start()
        job.complete({"accuracy": 0.95})
        
        job_dict = job.to_dict()
        
        assert job_dict["result"] == {"accuracy": 0.95}
        assert job_dict["error"] is None


class TestJobPriority:
    """Test Priority value object"""
    
    def test_priority_valid_range(self):
        """Test priority accepts valid range"""
        
        for p in range(1, 11):
            priority = Priority(p)
            assert priority.value == p
    
    def test_priority_below_min(self):
        """Test priority rejects below minimum"""
        
        with pytest.raises(ValueError):
            Priority(0)
    
    def test_priority_above_max(self):
        """Test priority rejects above maximum"""
        
        with pytest.raises(ValueError):
            Priority(11)
    
    def test_priority_comparison(self):
        """Test priority comparisons"""
        
        p1 = Priority(3)
        p2 = Priority(5)
        
        assert p1 < p2
        assert not (p1 == p2)
        assert p1.value < p2.value
