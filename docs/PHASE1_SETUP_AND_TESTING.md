# Phase 1: Asynchronous Polling Architecture - Setup & Testing Guide

**Date:** June 1, 2026  
**Status:** Phase 1 Implementation Complete

## Quick Start

### 1. Environment Setup

Set environment variables for AI Worker and API Service:

**AI Worker (.env):**
```env
FLASK_ENV=development
LOG_LEVEL=DEBUG
SERVICE_HOST=0.0.0.0
SERVICE_PORT=5001

# AI Worker Model Execution
AI_WORKER_MODEL_PATH=/app/models
AI_WORKER_GPU_ENABLED=false
AI_WORKER_MAX_WORKERS=4

# Celery (not used in Phase 1, but configured)
CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672/
CELERY_RESULT_BACKEND=redis://redis:6379/0
```

**API Service (.env):**
```env
FLASK_ENV=development
LOG_LEVEL=DEBUG
SERVICE_HOST=0.0.0.0
SERVICE_PORT=5000

# AI Worker Service
AI_WORKER_URL=http://localhost:5001
AI_WORKER_TIMEOUT_SECONDS=300
AI_WORKER_POLL_INTERVAL_SECONDS=2

# MongoDB
MONGODB_URI=mongodb://admin:admin123@localhost:27017/api_service?authSource=admin

# JWT (for API auth)
JWT_AUTH_ENABLED=true
JWT_AUTH_REQUIRED=false
JWT_SECRET_KEY=dev-secret-key
```

### 2. Start Services

**Terminal 1: Start MongoDB (if not already running)**
```bash
docker-compose up -d mongodb
```

**Terminal 2: Start AI Worker**
```bash
cd services/ai_worker
python -m flask run --port=5001
```

**Terminal 3: Start API Service**
```bash
cd services/api_service
python -m flask run --port=5000
```

### 3. Test Health Endpoints

```bash
# AI Worker health
curl http://localhost:5001/health
curl http://localhost:5001/api/v1/ai/capabilities

# API Service health
curl http://localhost:5000/health
```

## Running Integration Tests

### Unit Tests

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run specific test files
pytest tests/unit/ai_worker/ -v
pytest tests/unit/api_service/ -v
```

### Integration Tests (Phase 1)

```bash
# Run Phase 1 integration test
cd c:/Codes/AI_MICROSERVICES
python tests/integration/test_phase1_polling_architecture.py
```

Expected output:
```
╔════════════════════════════════════════════════════════════════════════════╗
║                    PHASE 1 INTEGRATION TESTS                              ║
╚════════════════════════════════════════════════════════════════════════════╝

[... test output ...]

╔════════════════════════════════════════════════════════════════════════════╗
║                         TEST SUMMARY                                      ║
╠════════════════════════════════════════════════════════════════════════════╣
║  ✓ PASS   Module Imports                                                  ║
║  ✓ PASS   JobManager                                                      ║
║  ✓ PASS   ModelExecutor                                                   ║
║  ✓ PASS   AIWorkerClient                                                  ║
║  ✓ PASS   DI Container                                                    ║
╠════════════════════════════════════════════════════════════════════════════╣
║  Total: 5 passed, 0 failed                                                ║
╚════════════════════════════════════════════════════════════════════════════╝
```

## Manual End-to-End Testing

### Scenario 1: Submit Job and Poll for Result

**Step 1: Create a job**
```bash
curl -X POST http://localhost:5000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "inference",
    "input_data": {
      "model_id": "sentiment_analysis",
      "model_version": "1.0",
      "input": [1.0, 2.0, 3.0]
    },
    "priority": 5,
    "timeout_seconds": 300
  }'
```

Response:
```json
{
  "success": true,
  "data": {
    "id": "job-uuid-here",
    "status": "pending",
    "job_type": "inference",
    "user_id": null,
    "priority": 5,
    "input_data": {...},
    "result": null,
    "error": null,
    "created_at": "2026-06-01T10:00:00Z"
  },
  "status": "success",
  "code": 201
}
```

**Step 2: Get job details**
```bash
curl http://localhost:5000/api/v1/jobs/job-uuid-here
```

**Step 3: Poll for status (submit to AI Worker first)**

First, let's check if the AI Worker has received the job by hitting its endpoint directly:

```bash
curl -X POST http://localhost:5001/api/v1/ai/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "sentiment_analysis",
    "model_version": "1.0",
    "input_data": {
      "input": [1.0, 2.0, 3.0]
    }
  }'
```

Response:
```json
{
  "job_id": "ai-job-uuid",
  "status": "pending",
  "created_at": "2026-06-01T10:00:00Z",
  "message": "Job submitted successfully. Poll GET /jobs/{job_id} for results."
}
```

**Step 4: Poll AI Worker for result**
```bash
# Check status
curl http://localhost:5001/api/v1/ai/jobs/ai-job-uuid/status

# Get full details
curl http://localhost:5001/api/v1/ai/jobs/ai-job-uuid
```

**Step 5: Poll through API Service**
```bash
curl http://localhost:5000/api/v1/jobs/job-uuid-here/status
```

### Scenario 2: List All Jobs

```bash
# List jobs
curl http://localhost:5000/api/v1/jobs

# List with filtering
curl http://localhost:5000/api/v1/jobs?status=pending&limit=10

# AI Worker job list
curl http://localhost:5001/api/v1/ai/jobs?limit=100
```

### Scenario 3: Cancel a Job

```bash
curl -X POST http://localhost:5000/api/v1/jobs/job-uuid-here/cancel
```

### Scenario 4: Get Queue Statistics

```bash
curl http://localhost:5001/api/v1/ai/jobs/stats
```

## File Structure

### New Files Created

```
services/ai_worker/src/
├── core/
│   ├── __init__.py                          # NEW
│   └── model_executor.py                    # NEW
├── infrastructure/jobs/
│   ├── __init__.py                          # NEW
│   └── job_manager.py                       # NEW
└── presentation/routes/
    ├── __init__.py                          # NEW
    └── jobs.py                              # NEW

services/api_service/src/
├── infrastructure/external/
│   ├── __init__.py                          # UPDATED
│   └── ai_worker_client.py                  # NEW
└── application/use_cases/job/
    └── create_job.py                        # UPDATED

services/ai_worker/models/
└── sentiment_analysis_v1.0/
    ├── metadata.json                        # NEW (sample)
    └── config.json                          # NEW (sample)

tests/integration/
└── test_phase1_polling_architecture.py      # NEW

docs/
└── ASYNC_POLLING_ARCHITECTURE.md            # NEW
└── PHASE1_SETUP_AND_TESTING.md             # NEW (this file)
```

## How the Flow Works

### Job Submission Flow

1. **Client** → `POST /api/v1/jobs` (API Service)
   - Create job with input_data containing model_id, model_version
   - Job saved to MongoDB with status "pending"

2. **API Service** → `POST /api/v1/ai/jobs` (AI Worker)
   - Submit job to AI Worker asynchronously
   - Store AI Worker job_id reference in MongoDB

3. **Response** → Client receives job_id
   - Client can now poll for results

### Job Polling Flow

1. **Client** → `GET /api/v1/jobs/{id}/status` (API Service)
   - Check MongoDB for cached status first
   - If terminal state (completed, failed), return result immediately

2. **API Service** → `GET /api/v1/ai/jobs/{id}/status` (AI Worker) [if needed]
   - If not cached, fetch fresh status from AI Worker
   - Update MongoDB with new status
   - Return to client

### AI Worker Execution Flow

1. **AI Worker** receives `POST /jobs`
   - Create job in JobManager (in-memory queue)
   - Return job_id to caller immediately (202 Accepted)

2. **AI Worker** [background process - future]
   - Pick job from queue
   - Load model from local filesystem
   - Execute inference
   - Store result in job queue
   - Mark job as completed

3. **Client** polls for result
   - `GET /jobs/{id}/status` returns result when ready

## Model Directory Structure

Models are stored locally:

```
services/ai_worker/models/
├── model_id_v1.0/
│   ├── config.json          # Model configuration
│   ├── metadata.json        # Model metadata
│   └── weights.pt           # Model weights (optional for now)
└── model_id_v2.0/
    ├── config.json
    ├── metadata.json
    └── weights.pt
```

**config.json** - Model configuration:
```json
{
  "model_id": "sentiment_analysis",
  "version": "1.0",
  "framework": "pytorch|tensorflow|sklearn",
  "input_dim": 768,
  "output_dim": 3
}
```

**metadata.json** - Model metadata:
```json
{
  "model_id": "sentiment_analysis",
  "version": "1.0",
  "framework": "pytorch",
  "input_schema": {...},
  "output_schema": {...},
  "gpu_required": false,
  "expected_latency_ms": 100
}
```

## Configuration Reference

### AI Worker Config (services/ai_worker/src/config.py)

| Env Variable | Default | Description |
|---|---|---|
| `FLASK_ENV` | development | Environment: development, staging, production |
| `LOG_LEVEL` | INFO | Logging level: DEBUG, INFO, WARNING, ERROR |
| `SERVICE_PORT` | 5000 | HTTP port for health/job endpoints |
| `AI_WORKER_MODEL_PATH` | /app/models | Directory where models are stored |
| `AI_WORKER_GPU_ENABLED` | true | Enable GPU for model execution |
| `AI_WORKER_MAX_WORKERS` | 4 | Max parallel workers (future) |

### API Service Config (services/api_service/src/config.py)

| Env Variable | Default | Description |
|---|---|---|
| `AI_WORKER_URL` | http://localhost:5001 | AI Worker service URL |
| `AI_WORKER_TIMEOUT_SECONDS` | 300 | Overall job timeout |
| `AI_WORKER_POLL_INTERVAL_SECONDS` | 2 | Initial polling interval (uses exponential backoff) |

## Monitoring & Debugging

### AI Worker Logs

```bash
# Check AI Worker logs
docker logs ai-worker

# With verbose logging
AI_WORKER_LOG_LEVEL=DEBUG python -m flask run --port=5001
```

### API Service Logs

```bash
# Check API Service logs
docker logs api-service

# With verbose logging
LOG_LEVEL=DEBUG python -m flask run --port=5000
```

### Check Job Queue Statistics

```bash
curl http://localhost:5001/api/v1/ai/jobs/stats
```

Example output:
```json
{
  "total_jobs": 42,
  "active_jobs": 3,
  "by_status": {
    "pending": 10,
    "running": 3,
    "completed": 29
  },
  "avg_execution_time_ms": 1234.5
}
```

### MongoDB Debug

```bash
# Connect to MongoDB
mongosh "mongodb://admin:admin123@localhost:27017/api_service"

# Check jobs collection
db.jobs.find().limit(10).pretty()
db.jobs.find({status: "completed"}).count()
```

## Troubleshooting

### Issue: AI Worker service not responding

```
Solution: 
1. Verify service is running: curl http://localhost:5001/health
2. Check logs: docker logs ai-worker
3. Verify port is correct: AI_WORKER_URL in API Service config
```

### Issue: Jobs stuck in "pending" status

```
Solution:
1. Check if AI Worker is processing jobs
2. Verify model exists in models/ directory
3. Check AI Worker logs for errors
4. Increase AI_WORKER_TIMEOUT_SECONDS if jobs are long-running
```

### Issue: Models not loading

```
Solution:
1. Verify model directory structure exists
2. Check metadata.json and config.json are valid JSON
3. Verify AI_WORKER_MODEL_PATH points to correct directory
4. Check logs for specific framework errors (PyTorch, TensorFlow)
```

### Issue: Polling timeout

```
Solution:
1. Increase AI_WORKER_TIMEOUT_SECONDS (default 300s)
2. Check job execution time with /stats endpoint
3. Verify model execution time is reasonable
4. Consider using webhook callbacks instead of polling (Phase 2)
```

## Next Steps (Phase 2)

When ready to implement Phase 2:

1. **Notification Service**
   - Implement email/webhook delivery channels
   - Create notification triggers on job completion
   - Initially use polling/callback, later migrate to events

2. **Event-Driven Migration Path**
   - RabbitMQ integration (already running in docker-compose)
   - Event publisher/consumer setup
   - Replace polling with events (zero refactoring in app logic)

See [ASYNC_POLLING_ARCHITECTURE.md](ASYNC_POLLING_ARCHITECTURE.md) Phase 2 section for details.

## References

- [ASYNC_POLLING_ARCHITECTURE.md](ASYNC_POLLING_ARCHITECTURE.md) - Full architecture documentation
- [REST_API_DESIGN.md](REST_API_DESIGN.md) - API design principles
- [TESTING.md](TESTING.md) - Testing strategies
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide
