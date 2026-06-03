"""
Background Worker Approach - Implementation Details

This document provides comprehensive technical details about how the background
worker executes jobs asynchronously using ThreadPoolExecutor.
"""

# BACKGROUND WORKER APPROACH
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


## 1. THREADING MODEL

### Current Implementation: ThreadPoolExecutor

```python
# From: ai_engine/infrastructure/workers/job_worker.py

class AIJobWorker:
    def __init__(
        self,
        orchestrator: AIJobOrchestrator,
        max_workers: int = 4,
        on_complete: Callable[[AIJob], None] | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._on_complete = on_complete  # hook for event publishing

    def enqueue(self, job_id: str) -> Future:
        """Submit job_id for async processing in thread pool."""
        future = self._executor.submit(self._run, job_id)
        return future

    def _run(self, job_id: str) -> AIJob:
        try:
            job = self._orchestrator.process_job(job_id)
            if self._on_complete:
                try:
                    self._on_complete(job)
                except Exception:
                    logger.exception("on_complete hook failed for job_id=%s", job_id)
            return job
        except Exception:
            logger.exception("Worker failed for job_id=%s", job_id)
            raise
```

### Thread Safety Guarantees

✅ **Thread-Safe Operations**
- MongoDB provides document-level atomicity
- Each job = one document = one thread
- Status transitions are atomic updates
- No shared mutable state between threads

❌ **Non-Thread-Safe Patterns to Avoid**
- Shared job lists (use MongoDB queries instead)
- In-memory caches (use MongoDB indexes)
- Shared executor across multiple app instances


### Concurrency Diagram

```
Main Thread (Flask Request)
│
├─ Receive request
├─ Validate input
├─ Create job in MongoDB (status: PENDING)
├─ Call worker.enqueue(job_id)
│  └─ executor.submit(_run, job_id)
│     └─ [Queued in ThreadPool]
│
└─ Return 202 Accepted immediately
  (Don't wait for execution)

ThreadPool Worker #1
├─ Pick job_id from queue
├─ Call orchestrator.process_job(job_id)
├─ Transition PENDING → RUNNING
├─ Update MongoDB (status: RUNNING)
├─ Execute AI task
├─ On success: Transition RUNNING → COMPLETED
├─ On failure: Transition RUNNING → FAILED
└─ Update MongoDB with result/error

ThreadPool Worker #2  [May execute concurrent job]
├─ Pick different job_id from queue
├─ Similar process...
└─

ThreadPool Worker #3  [Idle, waiting for queue]
ThreadPool Worker #4  [Idle, waiting for queue]
```

### Capacity Planning

```
Configuration: max_workers=4

Best Case (I/O Bound):
- Each worker spends 50% time waiting (network, model loading)
- Effective parallelism: ~8 jobs
- If job takes 10s, only 5s is CPU time

Worst Case (CPU Bound):
- Each worker spends 100% CPU time
- Effective parallelism: 4 jobs (1 per core)
- Throughput: 1 job per 10s = 6 jobs/min

Bottleneck Analysis:
- 4 workers with 10s jobs = 0.4 jobs/sec = 24 jobs/min
- If API receives >24 jobs/min, queue builds up
- MongoDB can handle much higher request rates (100s of req/sec)

Recommendation:
- Monitor ThreadPool queue depth
- Monitor job latency (pending → running latency)
- If queue grows, increase max_workers or migrate to Celery
```


## 2. JOB LIFECYCLE & STATE TRANSITIONS

### State Machine (Detailed)

```
┌──────────────────────────────────────────────────────────────────────┐
│                          Job Lifecycle                               │
└──────────────────────────────────────────────────────────────────────┘

CREATION
  │
  ├─ Main Thread
  │  ├─ POST /api/v1/ai/summarize
  │  ├─ Validate request (Pydantic schema)
  │  ├─ Extract parameters
  │  ├─ Call use case
  │  │  ├─ orchestrator.submit_job()
  │  │  │  └─ Create AIJob {
  │  │  │     job_id: "uuid",
  │  │  │     job_type: "summarization",
  │  │  │     status: "pending",
  │  │  │     payload: {...},
  │  │  │     created_at: now,
  │  │  │     updated_at: now
  │  │  │  }
  │  │  │
  │  │  └─ repository.save(job)
  │  │     └─ MongoDB: Insert document
  │  │
  │  ├─ worker.enqueue(job_id)
  │  │  └─ executor.submit(_run, job_id)
  │  │     └─ ThreadPool: Add to queue
  │  │
  │  └─ Return 202 to client {job_id, status: "pending"}

QUEUEING
  │
  ├─ ThreadPool Queue
  │  ├─ Job waits for available worker
  │  ├─ Latency: 0ms to 100ms (depending on load)
  │  └─ Status in MongoDB: "pending"

EXECUTION START
  │
  ├─ Worker Thread [#1, #2, #3, or #4]
  │  ├─ Pick job_id from queue
  │  ├─ orchestrator.process_job(job_id)
  │  │  ├─ repository.get_by_id(job_id)
  │  │  │  └─ MongoDB: Read current job
  │  │  │
  │  │  ├─ job.mark_running()
  │  │  │  └─ job.status = "running"
  │  │  │     job.updated_at = now
  │  │  │
  │  │  └─ repository.update(job)
  │  │     └─ MongoDB: Update document
  │  │        {status: "pending" → "running"}
  │  │
  │  ├─ [Visible to polling clients: "running"]
  │  │
  │  ├─ orchestrator._resolve_task(job_type)
  │  │  └─ task_registry["summarization"] → SummarizationTask
  │  │
  │  ├─ task.execute(job.payload)
  │  │  ├─ Load model from disk
  │  │  ├─ Pre-process input
  │  │  ├─ Run inference
  │  │  ├─ Post-process output
  │  │  └─ Return AIJobResult {
  │  │     success: true,
  │  │     data: {summary: "..."},
  │  │     metadata: {...}
  │  │  }

COMPLETION (SUCCESS)
  │
  ├─ orchestrator.process_job() continued
  │  ├─ result.success == true
  │  │
  │  ├─ job.mark_completed(result)
  │  │  └─ job.status = "completed"
  │  │     job.result = {...}
  │  │     job.updated_at = now
  │  │
  │  ├─ repository.update(job)
  │  │  └─ MongoDB: Update document
  │  │     {status: "running" → "completed",
  │  │      result: {...}}
  │  │
  │  └─ [Visible to polling clients: "completed"]
  │
  ├─ worker._run() continued
  │  ├─ if self._on_complete:
  │  │  └─ self._on_complete(job)
  │  │     └─ Trigger event publishing (if configured)
  │  │
  │  └─ return job  [Worker thread ends]

COMPLETION (FAILURE)
  │
  ├─ orchestrator.process_job() error handling
  │  ├─ catch ValueError (validation error)
  │  │  └─ self._fail_job(job, str(exc))
  │  │
  │  ├─ catch Exception (unexpected error)
  │  │  └─ self._fail_job(job, f"Unexpected error: {exc}")
  │  │
  │  ├─ _fail_job(job, error_message)
  │  │  ├─ if job.status == "pending":
  │  │  │  └─ job.mark_running()  [Ensure RUNNING before FAILED]
  │  │  │
  │  │  └─ job.mark_failed(error_message)
  │  │     └─ job.status = "failed"
  │  │        job.error = error_message
  │  │        job.updated_at = now
  │  │
  │  ├─ repository.update(job)
  │  │  └─ MongoDB: Update document
  │  │     {status: "running" → "failed",
  │  │      error: "..."}
  │  │
  │  └─ [Visible to polling clients: "failed"]
  │
  ├─ worker._run() continued
  │  ├─ except Exception:
  │  │  ├─ logger.exception("Worker failed...")
  │  │  └─ raise  [Propagate to executor]
  │  │
  │  └─ [Executor logs exception, thread ends]

FINAL STATE
  │
  ├─ MongoDB document: {status: "completed" | "failed"}
  ├─ Client polling: Detects terminal state, stops polling
  ├─ No further updates for this job
  └─ ThreadPool worker: Available for next job
```

### Python Code Example (Detailed Flow)

```python
# File: ai_engine/application/orchestrator.py

def process_job(self, job_id: str) -> AIJob:
    """
    Execute the job synchronously (called by a background worker).
    
    Drives the full PENDING → RUNNING → COMPLETED | FAILED lifecycle.
    """
    # STEP 1: LOAD
    job = self._load_job(job_id)
    logger.debug(f"Loaded job: {job_id} (status: {job.status})")

    try:
        # STEP 2: VALIDATE
        task = self._resolve_task(job.job_type)
        task.validate_payload(job.payload)
        logger.debug(f"Validation passed for {job_id}")

        # STEP 3: MARK RUNNING & PERSIST
        job.mark_running()
        self._repo.update(job)
        logger.info(f"Job started: job_id={job_id}")

        # STEP 4: EXECUTE
        result: AIJobResult = task.execute(job.payload)
        logger.debug(f"Task executed for {job_id}: success={result.success}")

        # STEP 5: MARK TERMINAL STATE & PERSIST
        if result.success:
            job.mark_completed(result)
            logger.info(f"Job completed: job_id={job_id}")
        else:
            job.mark_failed(result.error or "Task returned failure without a message.")
            logger.warning(f"Job failed (task error): job_id={job_id} error={result.error}")

    except ValueError as exc:
        self._fail_job(job, str(exc))
        logger.warning(f"Job failed (validation): job_id={job_id} error={exc}")
    except Exception as exc:
        self._fail_job(job, f"Unexpected error: {exc}")
        logger.exception(f"Job failed (unexpected): job_id={job_id}")

    # STEP 6: FINAL PERSISTENCE
    self._repo.update(job)
    logger.debug(f"Job persisted: {job_id} (status: {job.status})")
    
    return job
```


## 3. MONGODB CONSISTENCY MODEL

### Document Layout

```json
{
  "_id": ObjectId("507f1f77bcf86cd799439011"),  // Mongo internal ID (auto)
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",  // Our UUID (unique index)
  "job_type": "summarization",
  "status": "completed",  // Index: for status queries
  "payload": {
    "text": "Artificial intelligence...",
    "max_new_tokens": 150
  },
  "result": {
    "summary": "AI has transformed...",
    "original_word_count": 68,
    "summary_word_count": 8,
    "compression_ratio": 0.12
  },
  "error": null,
  "tags": {
    "tenant": "acme",
    "project": "newsletter"
  },
  "created_at": ISODate("2026-06-02T10:00:00Z"),  // Index: for time queries
  "updated_at": ISODate("2026-06-02T10:00:08Z")
}
```

### Index Strategy

```javascript
// Indexes created automatically by MongoAIJobRepository._ensure_indexes()

db.ai_jobs.createIndex({ job_id: 1 }, { unique: true });
//  ↑ For fast by-id lookups, prevents duplicates

db.ai_jobs.createIndex({ status: 1 });
//  ↑ For status queries: get all "pending" jobs

db.ai_jobs.createIndex({ created_at: 1 });
//  ↑ For time-range queries and sorting
```

### Atomicity Guarantees

```python
# MongoDB document-level atomicity (single-document transactions)

# ATOMIC WRITE
self._repo.update(job)
└─ db.ai_jobs.replace_one(
    {"job_id": job_id},
    {...full job document...}
  )
  ├─ Atomically replaces entire document
  ├─ Concurrent reads see either old or new state
  ├─ Never see partial updates
  └─ Prevents inconsistency

# ATOMIC READ
job = self._repo.get_by_id(job_id)
└─ db.ai_jobs.find_one({"job_id": job_id})
  ├─ Reads entire document atomically
  ├─ Consistent snapshot at read time
  └─ No partial reads possible
```

### Consistency in Concurrent Scenarios

```
Scenario 1: Two Threads Trying to Update Same Job
──────────────────────────────────────────────────

Thread A (Status: PENDING → RUNNING)
│
├─ Read job from MongoDB: {status: "pending"}
│
├─ Change status to "running"
│
├─ Write back: replace_one({job_id}, {...})
│
└─ ✓ Success: Document updated to {status: "running"}

Thread B (Somehow also trying to update - shouldn't happen)
│
├─ [Blocked or didn't happen - only one job_id per thread]
│
└─ [Not a real scenario because each job runs on only one thread]

MongoDB Guarantee:
  ✓ Document-level atomicity
  ✓ No partial updates
  ✓ Consistent state maintained


Scenario 2: Reader During Writer (Polling Client)

Main Thread (Worker)               Client Thread (Polling)
│                                  │
├─ Update PENDING → RUNNING        ├─ GET /jobs/{id}
│  └─ replace_one(...)              │  └─ find_one({job_id})
│     ├─ Delete old doc                │
│     └─ Insert new doc                │  
│                                      └─ Reads: {status: "running"} ✓
│     (atomically replaced)            
│
├─ Update RUNNING → COMPLETED      ├─ [Waits 2s]
│  └─ replace_one(...)              │
│     ├─ Delete old doc                ├─ GET /jobs/{id}
│     └─ Insert new doc                │  └─ find_one({job_id})
│                                      │
│     (atomically replaced)            └─ Reads: {status: "completed", result: {...}} ✓

MongoDB Guarantee:
  ✓ Polling client never sees partial updates
  ✓ Client sees consistent snapshots
  ✓ No "dirty reads"
```


## 4. ERROR HANDLING & FAILURE MODES

### Task Validation Errors

```python
# When task input is invalid

try:
    task = self._resolve_task(job.job_type)
    task.validate_payload(job.payload)  # ← May raise ValueError
except ValueError as exc:
    self._fail_job(job, str(exc))
    # Result: job.status = "failed", job.error = "Invalid payload"
```

### Task Execution Errors

```python
# When task fails during inference

try:
    result: AIJobResult = task.execute(job.payload)
    
    if result.success:
        job.mark_completed(result)
    else:
        # Task returned result.success = False
        job.mark_failed(result.error or "Task returned failure")
except Exception as exc:
    self._fail_job(job, f"Unexpected error: {exc}")
    # Result: job.status = "failed", job.error includes exception message
```

### Unknown Errors

```python
# When anything unexpected happens

try:
    # ... job processing ...
except Exception as exc:
    self._fail_job(job, f"Unexpected error: {exc}")
    logger.exception(f"Job failed (unexpected): job_id={job_id}")
    # Result: job.status = "failed", preserved for analysis
```

### Error Visibility to Clients

```json
// When polling after failure

GET /api/v1/jobs/3fa85f64-5717-4562-b3fc-2c963f66afa6

{
  "status": "success",
  "code": 200,
  "data": {
    "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "job_type": "summarization",
    "status": "failed",
    "created_at": "2026-06-02T10:00:00Z",
    "updated_at": "2026-06-02T10:00:01Z",
    "result": null,
    "error": "Invalid input: text must contain at least 20 words"
  }
}
```


## 5. SCALABILITY & MIGRATION PATH

### Current Limitations (ThreadPoolExecutor)

| Aspect | Limit | Impact |
|--------|-------|--------|
| Workers | 4 | ~24 jobs/min with 10s tasks |
| Machine | Single | Can't scale across servers |
| Persistence | MongoDB | Bottleneck at ~10k jobs/min |
| Monitoring | Manual | No built-in metrics |
| Retries | None | Failed jobs stay failed |

### Migration Path to Celery

```python
# TODAY: ThreadPoolExecutor in Flask process
# ├─ Single machine
# ├─ Limited to 4-8 concurrent jobs
# └─ Simple to deploy

# PHASE 1: Celery + RabbitMQ
# ├─ Multiple worker nodes
# ├─ Unlimited concurrent jobs
# ├─ Task retries and scheduling
# └─ Requires additional deployment

# PHASE 2: Kubernetes + Celery
# ├─ Auto-scaling workers
# ├─ Load balancing
# ├─ Health checks
# └─ Highest complexity
```

### Drop-In Replacement Strategy

```python
# Abstract Worker Interface (Today: AIJobWorker)

class AbstractJobWorker:
    def enqueue(self, job_id: str) -> Future:
        """Submit job for async execution"""
        ...
    
    def get_status(self, job_id: str) -> JobStatus:
        """Check job status"""
        ...
    
    def shutdown(self, wait: bool = True) -> None:
        """Graceful shutdown"""
        ...

# Current: ThreadPoolExecutor
class AIJobWorker(AbstractJobWorker):
    def __init__(self, orchestrator, max_workers=4):
        self._executor = ThreadPoolExecutor(max_workers)
    
    def enqueue(self, job_id: str) -> Future:
        return self._executor.submit(self._run, job_id)

# Future: Celery (no change to use case layer!)
class CeleryJobWorker(AbstractJobWorker):
    def __init__(self, orchestrator):
        self._app = Celery()
    
    def enqueue(self, job_id: str) -> Future:
        return self._app.send_task('process_job', args=[job_id])

# Use case layer sees no difference!
adapter = SyncWorkerAdapter(CeleryJobWorker(...))
use_case = SubmitSummarizeUseCase(worker=adapter)
```
"""
