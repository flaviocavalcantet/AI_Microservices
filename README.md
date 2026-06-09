# AI Microservices Platform

Production-grade Python backend demonstrating **Clean Architecture** and **microservices** patterns. Built with Flask, MongoDB, RabbitMQ, Celery, and Docker/Kubernetes.

The repo has two complementary layers:
- **`ai_engine/`** — a self-contained AI processing module you can run standalone (Flask + MongoDB, no Docker needed)
- **`services/`** — a full four-service microservices platform wired together with RabbitMQ and deployable to Kubernetes

---

## Full platform (all microservices)

```bash
# 1. Copy and configure environment
cp config/environments/.env.development .env

# 2. Start all services
docker-compose up -d

# 3. View logs
docker-compose logs -f

# 4. Run tests
pytest

# 5. Stop
docker-compose down
```

### Submit a job and poll the result

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

# Poll status / result
curl http://localhost:5000/api/ai/jobs/<job_id>
```

Jobs are executed asynchronously via a `ThreadPoolExecutor` (4 workers by default). Status transitions: `PENDING → RUNNING → COMPLETED | FAILED`.

### Service ports

| Service | URL | Description |
|---------|-----|-------------|
| API | http://localhost:5000 | Main gateway & orchestration |
| Auth | http://localhost:5001 | JWT authentication & RBAC |
| AI Worker | http://localhost:5002 | Async AI/ML task processing |
| Notifications | http://localhost:5003 | Email & push delivery |
| RabbitMQ UI | http://localhost:15672 | Message broker dashboard |
| Flower | http://localhost:5555 | Celery task monitor |

---

## Architecture

Every service follows Clean Architecture with a strict inward dependency rule:

```
Presentation   → HTTP routes, middleware, serializers
Application    → Use cases, DTOs, orchestration
Domain         → Entities, repository interfaces, business logic (zero framework imports)
Infrastructure → MongoDB, RabbitMQ, external service clients
```

Services communicate asynchronously through RabbitMQ domain events — no direct DB sharing, no synchronous service-to-service calls in the hot path.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for full design decisions.

---

## Repository layout

```
AI_MICROSERVICES/
├── ai_engine/              # Standalone AI module (domain/application/infrastructure/interfaces)
│   └── application/tasks/  # summarization, sentiment_analysis, dataset_profiling
├── services/               # Microservices (api_service, auth_service, ai_worker, notification_service)
├── shared/                 # shared_kernel, shared_events, shared_utils
├── infrastructure/         # Docker images, Kubernetes manifests
├── config/environments/    # .env templates per environment
├── scripts/                # dev, testing, and deployment shell scripts
├── docs/                   # Architecture, API spec, DB schema, deployment guide
├── tests/                  # Root-level integration and e2e tests
├── app.py                  # Flask factory for standalone ai_engine
├── docker-compose.yml      # Local full-platform orchestration
└── pyproject.toml          # Project metadata and tool config
```

---

## Running tests

```bash
pytest                            # all tests
pytest tests/unit                 # unit only (no DB needed)
pytest tests/integration          # integration tests
pytest --cov=ai_engine --cov=services  # with coverage report
```

---

## Adding a new AI task to `ai_engine`

1. Add `MY_NEW_TASK = "my_new_task"` to `AIJobType` in `ai_engine/domain/models.py`.
2. Create `ai_engine/application/tasks/my_new_task.py` extending `BaseAITask`.
3. Register it in `ai_engine/infrastructure/container.py` inside `task_registry`.

No other files need to change — the orchestrator, worker, and REST layer pick it up automatically.

---

## Tech stack

Python 3.12 · Flask · MongoDB · RabbitMQ · Celery · Docker · Kubernetes · pytest · mypy · black

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — design decisions and trade-offs
- [`docs/API_SPECIFICATION.md`](docs/API_SPECIFICATION.md) — REST endpoint reference
- [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md) — data models
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — Docker and Kubernetes deployment
- [`docs/TESTING.md`](docs/TESTING.md) — testing strategy and patterns
- [`docs/AUTHENTICATION.md`](docs/AUTHENTICATION.md) — JWT and identity propagation
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — coding standards and PR process
