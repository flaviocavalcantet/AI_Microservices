# AI Processing Engine

Clean-architecture AI micro-service with Flask + MongoDB.

## Structure

```
ai_engine/
├── domain/              # Pure Python – models, repo interfaces
│   ├── models.py        # AIJob, AIJobType, AIJobStatus, AIJobResult
│   └── repositories.py  # AIJobRepository (abstract port)
├── application/         # Use-cases & task abstractions
│   ├── base_task.py     # BaseAITask (contract for every AI task)
│   ├── orchestrator.py  # AIJobOrchestrator (lifecycle manager)
│   └── tasks/
│       ├── summarization.py
│       ├── sentiment_analysis.py
│       └── dataset_profiling.py
├── infrastructure/      # Framework-specific adapters
│   ├── persistence/
│   │   └── mongo_repository.py  # MongoAIJobRepository
│   ├── workers/
│   │   └── job_worker.py        # AIJobWorker (ThreadPoolExecutor)
│   └── container.py             # Dependency wiring / factory
└── interfaces/
    └── flask_routes.py  # REST Blueprint
```

## Quickstart

```bash
pip install -r requirements.txt
export MONGO_URI=mongodb://localhost:27017/ai_engine
export FLASK_APP=app:create_app
flask run
```

## Running tests

```bash
pytest                      # all tests
pytest tests/unit           # unit only (no DB needed)
pytest --cov=ai_engine      # with coverage
```

## Submit a job

```bash
# Summarization
curl -X POST http://localhost:5000/api/ai/jobs \
  -H "Content-Type: application/json" \
  -d '{"job_type":"summarization","payload":{"text":"Your long text here...","max_sentences":2}}'

# Sentiment analysis
curl -X POST http://localhost:5000/api/ai/jobs \
  -H "Content-Type: application/json" \
  -d '{"job_type":"sentiment_analysis","payload":{"text":"This product is absolutely great!"}}'

# Dataset profiling
curl -X POST http://localhost:5000/api/ai/jobs \
  -H "Content-Type: application/json" \
  -d '{"job_type":"dataset_profiling","payload":{"data":[{"name":"Alice","age":30},{"name":"Bob","age":null}]}}'

# Poll result
curl http://localhost:5000/api/ai/jobs/<job_id>
```

## Adding a new AI task

1. Add `MY_NEW_TASK = "my_new_task"` to `AIJobType` enum in `domain/models.py`.
2. Create `application/tasks/my_new_task.py` extending `BaseAITask`.
3. Register it in `infrastructure/container.py` inside `task_registry`.

That's it — no other files change.
