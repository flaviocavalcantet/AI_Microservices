# Asynchronous Job Execution with Polling Architecture

**Date:** May 29, 2026  
**Status:** Implementation Plan  
**Author:** AI Microservices Team

## Executive Summary

This document outlines the implementation approach for asynchronous AI worker job execution using a polling-based architecture. We defer RabbitMQ/event-driven architecture to Phase 2, focusing initially on:

1. **Phase 1**: Asynchronous job execution via HTTP polling (no RabbitMQ)
2. **Phase 2**: Notification service implementation + event-driven migration path

Models are stored locally on the filesystem. When event-driven architecture is needed, polling mechanisms will be replaced with RabbitMQ events with minimal refactoring.

---

## Architecture Overview

### Current State (Before Implementation)
- RabbitMQ container running but not wired
- Event contracts designed but not implemented
- AI worker has placeholder runner (`NotImplementedError`)
- Celery task handlers only partially sketched
- Event publisher registered as `None` (no-op)

### Target State (After Phase 1)
```
API Service                 AI Worker                    MongoDB
    |                           |                           |
    | POST /jobs {payload}      |                           |
    |-------------------------->|                           |
    |                           | return {job_id}           |
    | {job_id}                  |                           |
    |<--------------------------|                           |
    |                           |                           |
    | GET /jobs/{id}/status     | [async execution]        |
    |-------------------------->| [load model locally]      |
    |                           | [perform inference]       |
    | {status, result?}         |                           |
    |<--------------------------|                           |
    |                           | [save result]             |
    |                           |-------------------------->|
    |                           |                           |
```

### Target State (After Phase 2)
Notification service integrated via polling callback:
```
AI Worker                   Notification Service        Email/Webhook
    |                            |                            |
    | [job completes]            |                            |
    | trigger notification       |                            |
    |-------------------------->|                            |
    |                            | send email                 |
    |                            |--------------------------->|
```

Later, replace polling → RabbitMQ events (drop-in replacement).

---

## Phase 1: Asynchronous Job Execution (Polling)

### 1.1 AI Worker: Model Executor

**File:** `services/ai_worker/src/core/model_executor.py`

- Load AI models from local filesystem
- Perform inference on input data
- GPU detection and device management
- Model versioning and metadata

**Key Methods:**
```python
class ModelExecutor:
    def __init__(self, model_path: str)
    def load_model(self, model_id: str, version: str) -> bool
    def execute(self, input_data: dict) -> dict  # returns {result, metadata}
    def get_device() -> str  # cpu, gpu, etc.
```

**Model Storage Structure:**
```
services/ai_worker/models/
├── model_v1.0/
│   ├── weights.pt
│   ├── config.json
│   └── metadata.json
├── model_v1.1/
│   └── ...
└── model_v2.0/
    └── ...
```

### 1.2 AI Worker: Job Queue & Persistence

**File:** `services/ai_worker/src/infrastructure/jobs/job_manager.py`

- In-memory or SQLite job queue (decide based on requirements)
- Track job state: `pending` → `running` → `completed` | `failed`
- Store job metadata and results
- Job lifecycle management (creation, execution, cleanup)

**Key Methods:**
```python
class JobManager:
    def create_job(self, payload: dict) -> str  # returns job_id
    def get_job(self, job_id: str) -> Job
    def update_job_status(self, job_id: str, status: str, result: dict = None)
    def list_jobs(self, status: str = None) -> List[Job]
    def cleanup_old_jobs(self, retention_days: int = 7)
```

**Job Model:**
```python
@dataclass
class Job:
    id: str
    status: str  # pending, running, completed, failed
    payload: dict
    result: dict = None
    error: str = None
    created_at: datetime = None
    started_at: datetime = None
    completed_at: datetime = None
    model_id: str = None
    model_version: str = None
```

### 1.3 AI Worker: HTTP Endpoints

**File:** `services/ai_worker/src/presentation/routes/jobs.py`

**Endpoints:**

1. **POST /jobs** — Submit asynchronous job
   ```
   Request: {model_id, model_version, input_data}
   Response: {job_id, status: "pending", created_at}
   ```

2. **GET /jobs/{job_id}** — Get full job details
   ```
   Response: {id, status, payload, result, error, timestamps}
   ```

3. **GET /jobs/{job_id}/status** — Get only status
   ```
   Response: {job_id, status, result?, error?}
   ```

4. **GET /jobs** — List jobs (optional, with filtering)
   ```
   Query: ?status=pending&limit=100
   Response: [{id, status, created_at}, ...]
   ```

### 1.4 API Service: Async Job Client

**File:** `services/api_service/src/infrastructure/clients/ai_worker_client.py`

- Submit jobs to ai_worker asynchronously
- Poll for job completion
- Handle retries and timeouts
- Error handling and circuit breaking

**Key Methods:**
```python
class AIWorkerClient:
    def submit_job(self, model_id: str, model_version: str, input_data: dict) -> str
        # returns job_id
    
    def get_job_status(self, job_id: str) -> dict
        # returns {status, result?, error?}
    
    def poll_until_complete(self, job_id: str, timeout_seconds: int = 300, 
                           poll_interval_seconds: int = 2) -> dict
        # wait for job to complete, return result or raise timeout
```

### 1.5 API Service: Job Submission Use Case

**File:** `services/api_service/src/application/use_cases/submit_job.py`

- Accept job request from API caller
- Create job record in MongoDB
- Submit to ai_worker
- Return job_id to caller
- Store job_id reference in API database

**Flow:**
```python
class SubmitJobUseCase:
    def execute(self, user_id: str, model_id: str, input_data: dict) -> dict:
        # 1. Validate input
        # 2. Create job record in MongoDB
        # 3. Submit to ai_worker (get job_id)
        # 4. Link API job to ai_worker job_id
        # 5. Return job_id to caller
```

### 1.6 API Service: Job Status Polling Endpoint

**File:** `services/api_service/src/presentation/routes/jobs.py`

**Endpoints:**

1. **POST /jobs** — Submit job
   ```
   Request: {model_id, model_version, input_data}
   Response: {job_id, status: "pending"}
   ```

2. **GET /jobs/{job_id}/status** — Check job status
   ```
   Response: {job_id, status, result?, error?, progress?}
   ```

3. **GET /jobs/{job_id}** — Get full job details
   ```
   Response: {id, status, model_id, input_data, result, timestamps}
   ```

### 1.7 MongoDB Schema

**Collection: `jobs`**
```json
{
  "_id": "job_123abc",
  "user_id": "user_456",
  "model_id": "model_sentiment",
  "model_version": "1.0",
  "ai_worker_job_id": "aw_job_789xyz",
  "status": "completed",
  "input_data": {...},
  "result": {...},
  "error": null,
  "created_at": "2026-05-29T10:00:00Z",
  "started_at": "2026-05-29T10:00:05Z",
  "completed_at": "2026-05-29T10:00:15Z",
  "duration_ms": 10000
}
```

---

## Phase 2: Notification Service Integration

### 2.1 Notification Delivery Channels

**File:** `services/notification_service/src/infrastructure/notifications/email_channel.py`

- Send emails via SMTP or email service (SendGrid, etc.)
- Template rendering
- Retry logic

**File:** `services/notification_service/src/infrastructure/notifications/webhook_channel.py`

- Send HTTP webhook callbacks
- Retry with exponential backoff
- Payload signing (optional)

### 2.2 Job Completion Notifier

**File:** `services/notification_service/src/application/use_cases/notify_job_completed.py`

- Listen for job completion events (initially via polling/callback)
- Trigger notifications to user
- Track notification status

### 2.3 Notification Trigger Integration

**File:** `services/ai_worker/src/infrastructure/jobs/notification_hook.py` (new)

When job completes:
```python
def on_job_completed(job_id: str, result: dict):
    # 1. Get job metadata from MongoDB
    # 2. Call notification_service (HTTP POST)
    # 3. Log notification status
```

**Later (Phase 2.5):** Replace with RabbitMQ event publisher

---

## Phase 3 (Future): Event-Driven Migration

### Strategy

1. **Current (Polling):**
   ```
   api_service → ai_worker.POST /jobs → wait/poll
   ai_worker → notification_service.POST /notify (on completion)
   ```

2. **Future (RabbitMQ Events):**
   ```
   api_service → RabbitMQ JobSubmitted
   ai_worker → consumes JobSubmitted → publishes JobCompleted
   notification_service → consumes JobCompleted → sends notifications
   ```

### Abstraction Layer (prepare now)

**File:** `services/ai_worker/src/application/interfaces/job_executor.py`

```python
class IJobExecutor(ABC):
    @abstractmethod
    def submit_job(self, payload: dict) -> str: pass
    
    @abstractmethod
    def get_job_status(self, job_id: str) -> dict: pass
```

**Current Implementation (polling):**
```python
class PollingJobExecutor(IJobExecutor):
    # Current HTTP polling client
```

**Future Implementation (events):**
```python
class EventDrivenJobExecutor(IJobExecutor):
    # RabbitMQ-based executor (to be created later)
```

---

## Implementation Checklist

### Phase 1

#### AI Worker
- [ ] Implement `ModelExecutor` with local model loading
- [ ] Create `JobManager` (job queue, state tracking)
- [ ] Implement `POST /jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/status` endpoints
- [ ] Setup local model storage directory structure
- [ ] Test model loading and inference execution
- [ ] Test job queue persistence (in-memory or SQLite)

#### API Service
- [ ] Implement `AIWorkerClient` (job submission, polling)
- [ ] Create `SubmitJobUseCase` (API job creation + ai_worker submission)
- [ ] Implement `POST /jobs`, `GET /jobs/{id}/status` endpoints
- [ ] Create MongoDB schema for jobs collection
- [ ] Test end-to-end: submit → poll → complete
- [ ] Add error handling and timeouts

#### Database
- [ ] Create jobs collection indexes
- [ ] Define job TTL policy (auto-cleanup)

#### Testing
- [ ] Unit tests for `ModelExecutor`
- [ ] Unit tests for `JobManager`
- [ ] Integration tests for endpoints
- [ ] End-to-end tests (submit job via API, poll until complete)

### Phase 2

#### Notification Service
- [ ] Implement email delivery channel
- [ ] Implement webhook delivery channel
- [ ] Create `NotifyJobCompletedUseCase`
- [ ] Add notification trigger when job completes (via polling/callback)
- [ ] Test notification delivery

#### Documentation
- [ ] Document polling→events migration strategy
- [ ] Add architecture diagrams
- [ ] Create migration guide for Phase 3

#### Testing
- [ ] Notification delivery tests
- [ ] End-to-end job completion + notification

---

## Configuration & Environment Variables

### AI Worker
```env
AI_WORKER_MODEL_PATH=/app/models
AI_WORKER_GPU_ENABLED=true
AI_WORKER_DEVICE=auto  # auto, cpu, cuda, mps
AI_WORKER_MAX_WORKERS=4
MONGODB_URL=mongodb://mongo:27017
MONGODB_DB=ai_microservices
```

### API Service
```env
AI_WORKER_URL=http://ai_worker:5001
AI_WORKER_TIMEOUT_SECONDS=300
AI_WORKER_POLL_INTERVAL_SECONDS=2
MONGODB_URL=mongodb://mongo:27017
MONGODB_DB=ai_microservices
```

### Notification Service
```env
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@example.com
SMTP_PASSWORD=***
NOTIFICATION_WEBHOOK_TIMEOUT_SECONDS=10
MONGODB_URL=mongodb://mongo:27017
MONGODB_DB=ai_microservices
```

---

## Monitoring & Logging

### Key Metrics to Track

1. **Job execution time** (start → complete)
2. **Job success/failure rate**
3. **AI Worker utilization** (active jobs, queue depth)
4. **Polling latency** (time from submission → polling discovery of completion)
5. **Notification delivery success rate**

### Structured Logging

- Log job state transitions (pending → running → completed)
- Log model loading times
- Log inference times
- Log polling attempts and results
- Log notification delivery attempts

---

## Risk Analysis & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Polling overhead | Increased latency, API load | Exponential backoff, max polling duration |
| Job queue loss (in-memory) | Data loss on restart | Use SQLite or MongoDB for persistence |
| Long-running jobs | Client timeout | Document timeout limits, support WebSocket later |
| Model loading failure | Job failure | Validate models on startup, cache in memory |
| Notification delivery failure | User unaware of completion | Retry logic, webhook signing for reliability |
| RabbitMQ migration complexity | Refactoring effort | Abstract job executor interface (prepare now) |

---

## Success Criteria

✅ **Phase 1 Complete When:**
1. API can submit job via `POST /jobs` and receive job_id
2. AI worker processes job asynchronously
3. Caller polls API `GET /jobs/{id}/status` and receives result
4. Job metadata stored in MongoDB
5. Models load correctly from local filesystem
6. End-to-end test passes: submit → process → poll → complete

✅ **Phase 2 Complete When:**
1. Notification service can send emails/webhooks
2. Notifications triggered when jobs complete
3. Caller receives job completion notification
4. End-to-end test passes: submit → process → notify

✅ **Phase 3 Ready (Future):**
1. Abstraction layer in place (`IJobExecutor`)
2. Polling → events migration path documented
3. Zero refactoring needed in application logic when events added

---

## Future Considerations

1. **Job Queue Persistence:** In-memory vs. SQLite vs. MongoDB for job state?
2. **Polling Interval Strategy:** Fixed vs. exponential backoff vs. webhook callback?
3. **Job Retention:** How long to keep completed jobs? Cleanup strategy?
4. **Long-Running Jobs:** WebSocket support for real-time updates (Phase 4)?
5. **Model Versioning:** How to handle model updates without service restart?
6. **Distributed Execution:** Multiple AI workers (load balancing, job distribution)?
7. **Cost Optimization:** Auto-scaling workers based on queue depth?

---

## References

- [EVENT_CONTRACTS.md](EVENT_CONTRACTS.md) — Event contracts (for Phase 3)
- [REST_API_DESIGN.md](REST_API_DESIGN.md) — API design principles
- [CLEAN_ARCHITECTURE.md](CLEAN_ARCHITECTURE.md) — Architecture patterns
- [TESTING.md](TESTING.md) — Testing strategies
