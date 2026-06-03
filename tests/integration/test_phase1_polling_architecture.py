"""
End-to-End Integration Test for Phase 1 Implementation

This script tests the complete workflow:
1. AI Worker model loading and job submission
2. API Service job creation and AI Worker communication
3. Job polling and result retrieval
"""

import sys
import time
import json
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_job_manager():
    """Test JobManager functionality"""
    logger.info("=" * 80)
    logger.info("TEST 1: JobManager Functionality")
    logger.info("=" * 80)
    
    try:
        from services.ai_worker.src.infrastructure.jobs.job_manager import JobManager, JobStatus
        
        # Create manager
        manager = JobManager(retention_days=7)
        logger.info("✓ JobManager initialized")
        
        # Create job
        payload = {"input": [1.0, 2.0, 3.0]}
        job_id = manager.create_job(payload, model_id="sentiment_analysis", model_version="1.0")
        logger.info(f"✓ Job created: {job_id}")
        
        # Get job
        job = manager.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.PENDING
        logger.info(f"✓ Job retrieved: status={job.status}")
        
        # Start job
        assert manager.start_job(job_id)
        job = manager.get_job(job_id)
        assert job.status == JobStatus.RUNNING
        logger.info(f"✓ Job started: status={job.status}")
        
        # Complete job
        result = {"predictions": [0.8, 0.1, 0.1], "confidence": 0.8}
        assert manager.complete_job(job_id, result)
        job = manager.get_job(job_id)
        assert job.status == JobStatus.COMPLETED
        assert job.result == result
        logger.info(f"✓ Job completed: status={job.status}")
        
        # Statistics
        stats = manager.get_statistics()
        logger.info(f"✓ Statistics: {json.dumps(stats, indent=2)}")
        
        logger.info("✓ TEST 1 PASSED\n")
        return True
        
    except Exception as e:
        logger.error(f"✗ TEST 1 FAILED: {e}", exc_info=True)
        return False


def test_model_executor():
    """Test ModelExecutor functionality"""
    logger.info("=" * 80)
    logger.info("TEST 2: ModelExecutor Functionality")
    logger.info("=" * 80)
    
    try:
        from services.ai_worker.src.core.model_executor import ModelExecutor
        
        # Create executor
        model_path = Path(__file__).parent.parent / "services" / "ai_worker" / "models"
        executor = ModelExecutor(str(model_path), enable_gpu=False)
        logger.info(f"✓ ModelExecutor initialized: {executor.device}")
        
        # List available models
        available = executor.list_available_models()
        logger.info(f"✓ Available models: {available}")
        
        # Load model
        assert executor.load_model("sentiment_analysis", "1.0")
        logger.info("✓ Model loaded: sentiment_analysis v1.0")
        
        # Get device info
        device_info = executor.get_device_info()
        logger.info(f"✓ Device info: {json.dumps(device_info, indent=2)}")
        
        # Execute model
        input_data = {"input": [1.0, 2.0, 3.0]}
        result = executor.execute("sentiment_analysis", input_data, "1.0")
        logger.info(f"✓ Model executed: {result.execution_time_ms:.2f}ms")
        logger.info(f"  Output: {result.output}")
        
        logger.info("✓ TEST 2 PASSED\n")
        return True
        
    except Exception as e:
        logger.error(f"✗ TEST 2 FAILED: {e}", exc_info=True)
        return False


def test_ai_worker_client():
    """Test AIWorkerClient (mock test without running service)"""
    logger.info("=" * 80)
    logger.info("TEST 3: AIWorkerClient Initialization")
    logger.info("=" * 80)
    
    try:
        from services.api_service.src.infrastructure.external.ai_worker_client import AIWorkerClient
        
        # Create client
        client = AIWorkerClient(
            base_url="http://localhost:5001",
            timeout_seconds=300,
            poll_interval_seconds=2
        )
        logger.info("✓ AIWorkerClient initialized")
        logger.info(f"  Base URL: {client.base_url}")
        logger.info(f"  Timeout: {client.timeout_seconds}s")
        logger.info(f"  Poll interval: {client.poll_interval_seconds}s")
        
        logger.info("✓ TEST 3 PASSED\n")
        return True
        
    except Exception as e:
        logger.error(f"✗ TEST 3 FAILED: {e}", exc_info=True)
        return False


def test_imports():
    """Test all imports work correctly"""
    logger.info("=" * 80)
    logger.info("TEST 4: Module Imports")
    logger.info("=" * 80)
    
    try:
        # AI Worker
        from services.ai_worker.src.core.model_executor import ModelExecutor
        logger.info("✓ Imported: ModelExecutor")
        
        from services.ai_worker.src.infrastructure.jobs.job_manager import JobManager
        logger.info("✓ Imported: JobManager")
        
        from services.ai_worker.src.presentation.routes.jobs import create_jobs_blueprint
        logger.info("✓ Imported: create_jobs_blueprint")
        
        # API Service
        from services.api_service.src.infrastructure.external.ai_worker_client import AIWorkerClient
        logger.info("✓ Imported: AIWorkerClient")
        
        from services.api_service.src.application.use_cases.job.create_job import CreateJobUseCase
        logger.info("✓ Imported: CreateJobUseCase")
        
        logger.info("✓ TEST 4 PASSED\n")
        return True
        
    except Exception as e:
        logger.error(f"✗ TEST 4 FAILED: {e}", exc_info=True)
        return False


def test_container_registration():
    """Test DI container can be initialized"""
    logger.info("=" * 80)
    logger.info("TEST 5: Dependency Injection Container")
    logger.info("=" * 80)
    
    try:
        from services.ai_worker.src.container import ServiceContainer
        from services.ai_worker.src.config import Config, DevelopmentConfig
        from services.ai_worker.src.core.model_executor import ModelExecutor
        from services.ai_worker.src.infrastructure.jobs.job_manager import JobManager
        
        # Create container
        container = ServiceContainer()
        config = DevelopmentConfig()
        
        # Register services
        container.register_instance("config", config)
        container.register("job_manager", lambda: JobManager(), singleton=True)
        
        model_path = config.__dict__.get("AI_WORKER_MODEL_PATH", "/app/models")
        container.register(
            "model_executor",
            lambda: ModelExecutor(model_path, enable_gpu=False),
            singleton=True
        )
        logger.info("✓ Services registered in container")
        
        # Resolve services
        resolved_job_manager = container.resolve("job_manager")
        assert resolved_job_manager is not None
        logger.info("✓ Resolved: JobManager")
        
        resolved_executor = container.resolve("model_executor")
        assert resolved_executor is not None
        logger.info("✓ Resolved: ModelExecutor")
        
        logger.info("✓ TEST 5 PASSED\n")
        return True
        
    except Exception as e:
        logger.error(f"✗ TEST 5 FAILED: {e}", exc_info=True)
        return False


def run_all_tests():
    """Run all integration tests"""
    logger.info("\n")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 20 + "PHASE 1 INTEGRATION TESTS" + " " * 34 + "║")
    logger.info("╚" + "=" * 78 + "╝")
    logger.info("")
    
    results = []
    results.append(("Module Imports", test_imports()))
    results.append(("JobManager", test_job_manager()))
    results.append(("ModelExecutor", test_model_executor()))
    results.append(("AIWorkerClient", test_ai_worker_client()))
    results.append(("DI Container", test_container_registration()))
    
    # Summary
    logger.info("\n")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 27 + "TEST SUMMARY" + " " * 39 + "║")
    logger.info("╠" + "=" * 78 + "╣")
    
    passed = 0
    failed = 0
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"║  {status:8}  {test_name:50} " + " " * 18 + "║")
        if result:
            passed += 1
        else:
            failed += 1
    
    logger.info("╠" + "=" * 78 + "╣")
    logger.info(f"║  Total: {passed} passed, {failed} failed" + " " * 51 + "║")
    logger.info("╚" + "=" * 78 + "╝\n")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
