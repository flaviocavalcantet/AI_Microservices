"""
AI Worker HTTP Client

Communicates with AI Worker service to submit jobs and poll for results
"""

import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


@dataclass
class JobResult:
    """Result from AI worker job execution"""
    job_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    model_id: Optional[str] = None
    model_version: Optional[str] = None


class AIWorkerClient:
    """
    Client for communicating with AI Worker service
    
    Handles:
    - Job submission
    - Status polling
    - Error handling and retries
    - Request/response serialization
    """
    
    def __init__(self, base_url: str, timeout_seconds: int = 300, 
                 poll_interval_seconds: int = 2, max_retries: int = 3):
        """
        Initialize AI Worker Client
        
        Args:
            base_url: AI Worker service URL (e.g., http://ai_worker:5001)
            timeout_seconds: Overall timeout for operations
            poll_interval_seconds: Initial interval between polling requests
            max_retries: Max retries for failed requests
        """
        self.base_url = base_url.rstrip('/')
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.max_retries = max_retries
        self.session = self._create_session()
        
        logger.info(f"AIWorkerClient initialized: {self.base_url}")
    
    def _create_session(self) -> requests.Session:
        """Create requests session with retry strategy"""
        session = requests.Session()
        
        # Retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            backoff_factor=1
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def submit_job(self, model_id: str, input_data: Dict[str, Any],
                   model_version: str = "1.0") -> str:
        """
        Submit a job to AI Worker
        
        Args:
            model_id: Model to execute
            input_data: Input for the model
            model_version: Model version (default "1.0")
            
        Returns:
            Job ID
            
        Raises:
            ValueError: If submission fails
        """
        url = f"{self.base_url}/api/v1/ai/jobs"
        payload = {
            "model_id": model_id,
            "model_version": model_version,
            "input_data": input_data
        }
        
        try:
            logger.info(f"Submitting job: model={model_id}, version={model_version}")
            response = self.session.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            job_id = data.get("job_id")
            
            if not job_id:
                raise ValueError("No job_id in response")
            
            logger.info(f"Job submitted successfully: {job_id}")
            return job_id
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to submit job to {url}: {e}")
            raise ValueError(f"Failed to submit job: {e}")
        except (ValueError, KeyError) as e:
            logger.error(f"Invalid response from AI Worker: {e}")
            raise
    
    def get_job_status(self, job_id: str) -> JobResult:
        """
        Get job status from AI Worker
        
        Args:
            job_id: Job ID
            
        Returns:
            JobResult with current status and result (if available)
            
        Raises:
            ValueError: If job not found or request fails
        """
        url = f"{self.base_url}/api/v1/ai/jobs/{job_id}/status"
        
        try:
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 404:
                raise ValueError(f"Job not found: {job_id}")
            
            response.raise_for_status()
            
            data = response.json()
            
            return JobResult(
                job_id=data.get("job_id", job_id),
                status=data.get("status"),
                result=data.get("result"),
                error=data.get("error")
            )
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get job status for {job_id}: {e}")
            raise ValueError(f"Failed to get job status: {e}")
    
    def get_job_details(self, job_id: str) -> JobResult:
        """
        Get full job details from AI Worker
        
        Args:
            job_id: Job ID
            
        Returns:
            JobResult with full details
            
        Raises:
            ValueError: If job not found or request fails
        """
        url = f"{self.base_url}/api/v1/ai/jobs/{job_id}"
        
        try:
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 404:
                raise ValueError(f"Job not found: {job_id}")
            
            response.raise_for_status()
            
            data = response.json()
            
            return JobResult(
                job_id=data.get("id", job_id),
                status=data.get("status"),
                result=data.get("result"),
                error=data.get("error"),
                created_at=data.get("created_at"),
                started_at=data.get("started_at"),
                completed_at=data.get("completed_at"),
                model_id=data.get("model_id"),
                model_version=data.get("model_version")
            )
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get job details for {job_id}: {e}")
            raise ValueError(f"Failed to get job details: {e}")
    
    def poll_until_complete(self, job_id: str, timeout_seconds: Optional[int] = None,
                           poll_interval_seconds: Optional[float] = None) -> JobResult:
        """
        Poll AI Worker until job completes or timeout
        
        Args:
            job_id: Job ID
            timeout_seconds: Max time to wait (default: self.timeout_seconds)
            poll_interval_seconds: Interval between polls (default: self.poll_interval_seconds)
            
        Returns:
            Final JobResult
            
        Raises:
            TimeoutError: If job doesn't complete within timeout
            ValueError: If job fails or other error occurs
        """
        timeout_seconds = timeout_seconds or self.timeout_seconds
        poll_interval_seconds = poll_interval_seconds or self.poll_interval_seconds
        
        start_time = time.time()
        poll_count = 0
        current_interval = poll_interval_seconds
        
        logger.info(f"Polling job {job_id} (timeout: {timeout_seconds}s, "
                   f"poll interval: {poll_interval_seconds}s)")
        
        while True:
            elapsed = time.time() - start_time
            
            if elapsed > timeout_seconds:
                logger.error(f"Job polling timeout for {job_id} after {elapsed:.1f}s")
                raise TimeoutError(f"Job did not complete within {timeout_seconds} seconds")
            
            try:
                result = self.get_job_status(job_id)
                poll_count += 1
                
                if result.status == "completed":
                    logger.info(f"Job completed: {job_id} (polls: {poll_count}, "
                               f"time: {elapsed:.1f}s)")
                    return result
                
                if result.status == "failed":
                    logger.error(f"Job failed: {job_id} - {result.error}")
                    raise ValueError(f"Job failed: {result.error}")
                
                if result.status == "cancelled":
                    logger.warning(f"Job cancelled: {job_id}")
                    raise ValueError("Job was cancelled")
                
                # Job still running, wait before next poll
                if poll_count % 5 == 0:  # Log every 5 polls
                    logger.debug(f"Job still {result.status}: {job_id} "
                                f"(polls: {poll_count}, elapsed: {elapsed:.1f}s)")
                
                time.sleep(current_interval)
                
                # Exponential backoff (optional: cap at 5 seconds)
                current_interval = min(current_interval * 1.5, 5.0)
            
            except ValueError as e:
                # Re-raise job-specific errors (failed, cancelled, not found)
                if "failed" in str(e).lower() or "cancelled" in str(e).lower():
                    raise
                # Re-raise if it's not a retrieval error
                if "job not found" not in str(e).lower():
                    raise
                # Job not found - might still be processing, continue polling
                logger.debug(f"Job not yet available in worker: {job_id}")
                time.sleep(current_interval)
            
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Connection error polling job {job_id}, retrying: {e}")
                time.sleep(current_interval)
            
            except Exception as e:
                logger.error(f"Unexpected error polling job {job_id}: {e}")
                raise
    
    def list_jobs(self, status: Optional[str] = None, limit: int = 100) -> list:
        """
        List jobs from AI Worker
        
        Args:
            status: Filter by status (pending, running, completed, failed, cancelled)
            limit: Max jobs to return
            
        Returns:
            List of JobResult objects
            
        Raises:
            ValueError: If request fails
        """
        url = f"{self.base_url}/api/v1/ai/jobs"
        params = {"limit": limit}
        
        if status:
            params["status"] = status
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            jobs_data = data.get("jobs", [])
            
            return [JobResult(**job) for job in jobs_data]
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to list jobs: {e}")
            raise ValueError(f"Failed to list jobs: {e}")
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get job queue statistics from AI Worker
        
        Returns:
            Statistics dictionary
            
        Raises:
            ValueError: If request fails
        """
        url = f"{self.base_url}/api/v1/ai/jobs/stats"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get queue stats: {e}")
            raise ValueError(f"Failed to get queue stats: {e}")
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a pending/running job
        
        Args:
            job_id: Job ID
            
        Returns:
            True if cancelled successfully
            
        Raises:
            ValueError: If cancellation fails
        """
        url = f"{self.base_url}/api/v1/ai/jobs/{job_id}/cancel"
        
        try:
            response = self.session.post(url, timeout=10)
            
            if response.status_code == 404:
                raise ValueError(f"Job not found: {job_id}")
            
            if response.status_code == 409:
                raise ValueError("Cannot cancel job in current state")
            
            response.raise_for_status()
            logger.info(f"Job cancelled: {job_id}")
            return True
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to cancel job {job_id}: {e}")
            raise ValueError(f"Failed to cancel job: {e}")
