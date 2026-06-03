"""
Asynchronous AI Job Execution - Execution Flow & Polling Strategy

This document provides execution flow diagrams, polling patterns, and client integration guides.
"""

# EXECUTION FLOW DIAGRAM
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
## 1. COMPLETE REQUEST-RESPONSE FLOW (Timeline)

Time  Client Side                    API Service                        MongoDB                  ThreadPool
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────

T+0   POST /ai/summarize ──────────>
                                     ┌─ Validate request
                                     │  (Pydantic schema)
                                     │
                                     ├─ SyncWorkerAdapter.submit_job_sync()
                                     │  ├─ orchestrator.submit_job()
                                     │  │  └─ Create AIJob {status: PENDING}
                                     │  │
                                     │  └─ repository.save(job)
                                                                    ┌─ Insert document
                                                                    │  {job_id, status:"pending"}
                                                                    └─

T+1                                  ├─ worker.enqueue(job_id)
                                     │  └─ executor.submit(_run, job_id)  ┌──────────┐
                                     │                                    │  Queued  │
                                     │                                    └────┬─────┘
                                     │
                                     ├─ Return 202 Accepted
                  <─────────────────  │  {job_id, status:"pending",
                                     │   poll_url:"/api/v1/jobs/{job_id}"}

T+2   [Client waits ~2-5s]           [Job executes in thread]
                                                                         Worker picks up job
                                                                         ├─ orchestrator.process_job()
                                                                         │  ├─ Load job
                                                                         │  ├─ Mark RUNNING
                                                                         │  └─ repository.update()
                                                                         │     {status:"running"}
                                                                         │         ┌─ Update document
                                                                         │         └─

T+5   GET /api/v1/jobs/{job_id}───>
                                     ├─ GetJobUseCase.execute()
                                     │  └─ repository.get_by_id(job_id)
                                                                    ┌─ Find document
                                                                    │  {status:"running"}
                                     <─ Read result
                                     │
                  <──────────────────┤  Return 200 OK
                  {job_id,status:     │  {status:"running", result:null}
                   "running"}

                                                                         [Task execution continues]
                                                                         ├─ Load model
                                                                         ├─ Execute inference
                                                                         ├─ Collect result
                                                                         └─ Mark COMPLETED
                                                                            └─ repository.update()
                                                                               {status:"completed",
                                                                                result:{...}}
                                                                                    ┌─ Update document
                                                                                    └─

T+10  GET /api/v1/jobs/{job_id}───>
                                     ├─ GetJobUseCase.execute()
                                     │  └─ repository.get_by_id(job_id)
                                                                    ┌─ Find document
                                                                    │  {status:"completed",
                                                                    │   result:{...}}
                                     <─ Read result
                                     │
                  <──────────────────┤  Return 200 OK
                  {job_id,             │  {status:"completed",
                   status:              │   result:{summary:...}}
                   "completed",
                   result:{...}}

T+11  [Client processes result]
      [Done]
```


## 2. STATUS STATE MACHINE

```
                ┌─────────────────┐
                │   Job Created   │
                └────────┬────────┘
                         │ submit_job()
                         ↓
                  ┌─────────────┐
                  │   PENDING   │ ◄─ Initial state after submission
                  └──────┬──────┘    Visible at T+1 when polling
                         │
                    [enqueue]
                    ↓
              ┌──────────────────┐
              │ In ThreadPool     │
              │ Queue             │
              └────────┬─────────┘
                       │
                    [execute]
                    ↓
              ┌──────────────────┐
              │    RUNNING       │ ◄─ Visible when polling during execution
              └────────┬─────────┘
                       │
            ┌──────────┴──────────┐
            │                     │
        [success]             [failure]
            ↓                     ↓
       ┌──────────┐          ┌──────────┐
       │COMPLETED │          │  FAILED  │
       └──────────┘          └──────────┘
            ↑                     ↑
            │                     │
    result: {...}         error: "..."
    No polling needed     No polling needed
```

### Cancellation (Optional)
```
PENDING  ──[cancel]──>  CANCELLED
RUNNING  ──[cancel]──>  CANCELLED  (best effort)
(Terminal states can't be cancelled)
```


## 3. COMPONENT INTERACTION DIAGRAM

```
┌──────────────────────────────────────────────────────────────────┐
│                         Client Application                       │
│  (Browser, Mobile App, CLI, Microservice)                        │
└────────────────────┬─────────────────────────────────────────────┘
                     │
                     │ HTTP Request
                     ↓
┌──────────────────────────────────────────────────────────────────┐
│                      Flask API Service                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Routes / Controllers                                    │   │
│  │  - POST /api/v1/ai/summarize                             │   │
│  │  - POST /api/v1/ai/sentiment                             │   │
│  │  - POST /api/v1/ai/profile                               │   │
│  │  - GET  /api/v1/jobs/{job_id}                            │   │
│  └───────────────────┬──────────────────────────────────────┘   │
│                      │                                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Application Layer (Use Cases)                           │   │
│  │  - SubmitSummarizeUseCase                                │   │
│  │  - SubmitSentimentUseCase                                │   │
│  │  - SubmitProfileUseCase                                  │   │
│  │  - GetAIJobUseCase                                       │   │
│  └───────────────────┬──────────────────────────────────────┘   │
│                      │                                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Domain Layer (Orchestration)                            │   │
│  │  - AIJobOrchestrator                                     │   │
│  │    - submit_job()    → PENDING                           │   │
│  │    - process_job()   → RUNNING, COMPLETED, FAILED        │   │
│  │    - get_job()       → AIJob                             │   │
│  └───────────────────┬──────────────────────────────────────┘   │
│                      │                                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Worker & Execution                                      │   │
│  │  - AIJobWorker                                           │   │
│  │    - ThreadPoolExecutor (4 workers)                      │   │
│  │    - enqueue()  → submit to thread pool                  │   │
│  │    - _run()     → orchestrator.process_job()             │   │
│  │                                                          │   │
│  │  - Task Registry                                         │   │
│  │    - SummarizationTask                                   │   │
│  │    - SentimentAnalysisTask                               │   │
│  │    - DatasetProfilingTask                                │   │
│  └────────┬──────────────────────────────────────────────────┘  │
│           │                                                      │
└───────────┼──────────────────────────────────────────────────────┘
            │
            │ Read/Write Job Documents
            ↓
┌──────────────────────────────────────────────────────────────────┐
│                        MongoDB                                   │
│  Collection: ai_jobs                                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Document Schema                                         │   │
│  │  {                                                       │   │
│  │    _id: ObjectId,                                        │   │
│  │    job_id: "uuid",                                       │   │
│  │    job_type: "summarization",                            │   │
│  │    status: "pending|running|completed|failed",           │   │
│  │    payload: {...},                                       │   │
│  │    result: null | {...},                                 │   │
│  │    error: null | "...",                                  │   │
│  │    created_at: DateTime,                                 │   │
│  │    updated_at: DateTime,                                 │   │
│  │    tags: {...}                                           │   │
│  │  }                                                       │   │
│  │                                                          │   │
│  │  Indexes: job_id (unique), status, created_at            │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  [Job execution persists state changes atomically]              │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```


## 4. POLLING STRATEGIES

### 4.1 Aggressive Polling (for Real-time UX)

```javascript
// Browser-based polling (e.g., React, Vue.js)

class AIJobPoller {
  constructor(jobId, options = {}) {
    this.jobId = jobId;
    this.interval = options.interval || 500; // ms
    this.maxDuration = options.maxDuration || 5 * 60 * 1000; // 5 min
    this.onStatusChange = options.onStatusChange || (() => {});
    this.onComplete = options.onComplete || (() => {});
    this.onError = options.onError || (() => {});
  }

  async start() {
    const startTime = Date.now();
    let lastStatus = "pending";

    while (true) {
      try {
        const response = await fetch(`/api/v1/jobs/${this.jobId}`);
        const data = await response.json();
        const job = data.data;

        // Notify of status changes
        if (job.status !== lastStatus) {
          this.onStatusChange(job);
          lastStatus = job.status;
        }

        // Terminal states
        if (["completed", "failed", "cancelled"].includes(job.status)) {
          this.onComplete(job);
          break;
        }

        // Timeout check
        if (Date.now() - startTime > this.maxDuration) {
          this.onError(new Error("Job execution timeout"));
          break;
        }

        // Wait before next poll
        await new Promise(resolve => setTimeout(resolve, this.interval));
      } catch (error) {
        this.onError(error);
        break;
      }
    }
  }
}

// Usage
const poller = new AIJobPoller(jobId, {
  interval: 500,
  maxDuration: 5 * 60 * 1000,
  onStatusChange: (job) => {
    console.log(`Job status: ${job.status}`);
    // Update UI
  },
  onComplete: (job) => {
    if (job.status === "completed") {
      console.log("Result:", job.result);
    } else {
      console.error("Error:", job.error);
    }
  },
  onError: (error) => {
    console.error("Polling failed:", error);
  }
});

poller.start();
```

### 4.2 Moderate Polling (Balanced)

```python
# Python async polling (e.g., FastAPI, aiohttp)

import asyncio
import aiohttp
from datetime import datetime, timedelta

class JobPoller:
    def __init__(self, job_id, base_url="http://localhost:5000", 
                 interval=2, timeout_seconds=300):
        self.job_id = job_id
        self.base_url = base_url
        self.interval = interval
        self.timeout_seconds = timeout_seconds

    async def poll(self):
        """Poll job status until completion"""
        url = f"{self.base_url}/api/v1/jobs/{self.job_id}"
        start_time = datetime.now()
        
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    async with session.get(url) as resp:
                        data = await resp.json()
                        job = data["data"]
                        
                        print(f"Job status: {job['status']}")
                        
                        # Terminal state
                        if job["status"] in ["completed", "failed", "cancelled"]:
                            return job
                        
                        # Timeout
                        if (datetime.now() - start_time).total_seconds() > self.timeout_seconds:
                            raise TimeoutError(f"Job {self.job_id} execution timeout")
                        
                        # Wait before next poll
                        await asyncio.sleep(self.interval)
                
                except asyncio.TimeoutError:
                    raise
                except Exception as e:
                    print(f"Polling error: {e}")
                    raise

# Usage
poller = JobPoller(job_id, interval=2, timeout_seconds=300)
job = await poller.poll()
print(f"Final status: {job['status']}")
if job['status'] == 'completed':
    print(f"Result: {job['result']}")
```

### 4.3 Conservative Polling (Resource-conscious)

```bash
#!/bin/bash
# Shell script for polling (e.g., CLI tools)

JOB_ID=$1
BASE_URL="http://localhost:5000"
POLL_INTERVAL=10
MAX_ATTEMPTS=360  # 360 * 10s = 1 hour

for ((attempt=1; attempt<=MAX_ATTEMPTS; attempt++)); do
  response=$(curl -s "${BASE_URL}/api/v1/jobs/${JOB_ID}")
  status=$(echo "$response" | jq -r '.data.status')
  
  echo "[${attempt}] Job status: ${status}"
  
  case "$status" in
    "completed")
      result=$(echo "$response" | jq '.data.result')
      echo "✓ Job completed"
      echo "Result: $result"
      exit 0
      ;;
    "failed")
      error=$(echo "$response" | jq -r '.data.error')
      echo "✗ Job failed"
      echo "Error: $error"
      exit 1
      ;;
    "cancelled")
      echo "⊘ Job cancelled"
      exit 1
      ;;
    "pending"|"running")
      if [ $attempt -eq $MAX_ATTEMPTS ]; then
        echo "✗ Job timeout after $((MAX_ATTEMPTS * POLL_INTERVAL))s"
        exit 1
      fi
      echo "  [Next poll in ${POLL_INTERVAL}s]"
      sleep $POLL_INTERVAL
      ;;
  esac
done
```

### 4.4 Exponential Backoff Polling

```python
# Python with exponential backoff

import asyncio
import aiohttp
import math

class ExponentialBackoffPoller:
    def __init__(self, job_id, base_url="http://localhost:5000",
                 initial_interval=1, max_interval=30, multiplier=1.5):
        self.job_id = job_id
        self.base_url = base_url
        self.initial_interval = initial_interval
        self.max_interval = max_interval
        self.multiplier = multiplier

    async def poll(self, timeout_seconds=1800):
        """Poll with exponential backoff"""
        url = f"{self.base_url}/api/v1/jobs/{self.job_id}"
        interval = self.initial_interval
        elapsed = 0
        
        async with aiohttp.ClientSession() as session:
            while elapsed < timeout_seconds:
                try:
                    async with session.get(url) as resp:
                        data = await resp.json()
                        job = data["data"]
                        
                        print(f"Status: {job['status']} (interval: {interval:.1f}s)")
                        
                        if job["status"] in ["completed", "failed", "cancelled"]:
                            return job
                        
                        # Wait with exponential backoff
                        await asyncio.sleep(interval)
                        elapsed += interval
                        
                        # Increase interval
                        interval = min(interval * self.multiplier, self.max_interval)
                        
                except Exception as e:
                    print(f"Error: {e}")
                    raise
        
        raise TimeoutError(f"Job timeout after {timeout_seconds}s")

# Usage: Starts with 1s, grows to 30s
poller = ExponentialBackoffPoller(job_id)
job = await poller.poll(timeout_seconds=1800)  # 30 minutes
```


## 5. CURL EXAMPLES

### Submit Job
```bash
curl -X POST http://localhost:5000/api/v1/ai/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Your long document here...",
    "max_new_tokens": 150,
    "tags": {"project": "demo"}
  }'

# Response (202 Accepted):
# {
#   "status": "success",
#   "code": 202,
#   "data": {
#     "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
#     "status": "pending",
#     "poll_url": "/api/v1/jobs/3fa85f64-5717-4562-b3fc-2c963f66afa6"
#   }
# }
```

### Poll Job (Pending)
```bash
curl -s http://localhost:5000/api/v1/jobs/3fa85f64-5717-4562-b3fc-2c963f66afa6 | jq .

# Response (200 OK):
# {
#   "status": "success",
#   "code": 200,
#   "data": {
#     "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
#     "job_type": "summarization",
#     "status": "pending",
#     "created_at": "2026-06-02T10:00:00Z",
#     "updated_at": "2026-06-02T10:00:00Z",
#     "result": null,
#     "tags": {"project": "demo"}
#   }
# }
```

### Poll Job (Completed)
```bash
curl -s http://localhost:5000/api/v1/jobs/3fa85f64-5717-4562-b3fc-2c963f66afa6 | jq .

# Response (200 OK):
# {
#   "status": "success",
#   "code": 200,
#   "data": {
#     "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
#     "job_type": "summarization",
#     "status": "completed",
#     "created_at": "2026-06-02T10:00:00Z",
#     "updated_at": "2026-06-02T10:00:08Z",
#     "result": {
#       "summary": "AI has transformed how we interact with computers...",
#       "original_word_count": 68,
#       "summary_word_count": 8,
#       "compression_ratio": 0.12
#     },
#     "tags": {"project": "demo"}
#   }
# }
```


## 6. STATUS CODE MEANINGS

| HTTP Code | Scenario | Meaning |
|-----------|----------|---------|
| 202 Accepted | POST /ai/{endpoint} | Job submitted, execute asynchronously |
| 200 OK | GET /jobs/{id} | Job status retrieved |
| 404 Not Found | GET /jobs/{id} (invalid id) | Job does not exist |
| 400 Bad Request | POST with invalid data | Validation failed |
| 500 Server Error | Any endpoint | Internal server error |

### Response Body Status Field

| Status | HTTP Code | Result Field | Meaning |
|--------|-----------|--------------|---------|
| success | 202 | null | Job accepted for processing |
| success | 200 (pending/running) | null | Job is executing, poll again |
| success | 200 (completed) | {...} | Job finished, result available |
| success | 200 (failed) | null | Job failed, check error field |
| error | 4xx-5xx | null | Error occurred |
"""
