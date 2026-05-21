# REST API Architecture Overview

## Request Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                        HTTP REQUEST                              │
│  POST /api/v1/jobs                                              │
│  {                                                              │
│    "job_type": "model_training",                               │
│    "input_data": {...},                                        │
│    "priority": 5                                               │
│  }                                                              │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                     MIDDLEWARE: CORRELATION ID                   │
│  - Get X-Correlation-ID from headers or generate new UUID       │
│  - Store in Flask g (request-scoped)                            │
│  - g.correlation_id, g.request_id, g.user_id                   │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                   MIDDLEWARE: REQUEST VALIDATION                 │
│  - Parse JSON body                                              │
│  - Validate against CreateJobRequest Pydantic model            │
│  - Convert to validated model instance                          │
│  - Store in request.validated_data                              │
│  - If invalid: raise ValidationError → 400 Bad Request         │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                     ROUTE HANDLER                                 │
│  @validate_request_schema(CreateJobRequest)                     │
│  def create_job():                                              │
│      schema = request.validated_data  # Already validated       │
│      use_case = container.resolve("create_job_use_case")       │
│      job = use_case.execute(schema)                            │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                   APPLICATION LAYER (Use Case)                   │
│  CreateJobUseCase.execute(CreateJobDTO):                        │
│    1. Create domain entity: Job.create(...)                     │
│    2. Validate business rules (in entity)                       │
│    3. Call repository: repository.save(job)                     │
│    4. Publish events (optional)                                 │
│    5. Return saved job entity                                   │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                    DOMAIN LAYER (Entity)                          │
│  Job.create(...):                                               │
│    - Generate ID                                                │
│    - Set defaults                                               │
│    - Validate invariants                                        │
│    - Return immutable Job instance                              │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                   INFRASTRUCTURE LAYER                            │
│  MongoJobRepository.save(job):                                  │
│    1. Convert Job entity → MongoDB document                     │
│    2. Insert into MongoDB collection                            │
│    3. Map saved document → Job entity                           │
│    4. Return entity with ID, timestamps, etc.                   │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                    RESPONSE FORMATTING                            │
│  - Convert Job entity to JSON                                   │
│  - Wrap in response envelope:                                   │
│  {                                                              │
│    "status": "success",                                         │
│    "data": { ... job data ... },                               │
│    "correlation_id": "abc-123",                                │
│    "timestamp": "2026-05-20T10:30:45Z"                         │
│  }                                                              │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│              MIDDLEWARE: ERROR HANDLING (If Exception)            │
│  - Catch all exceptions                                         │
│  - Format error response with correlation ID                    │
│  - Log error with context                                       │
│  - Return appropriate HTTP status code                          │
│  On Exception:                                                  │
│  {                                                              │
│    "status": "error",                                           │
│    "error": {                                                   │
│      "code": "ERROR_CODE",                                      │
│      "message": "Human readable message",                       │
│      "details": { ... }                                         │
│    },                                                           │
│    "correlation_id": "abc-123",                                │
│    "timestamp": "2026-05-20T10:30:45Z"                         │
│  }                                                              │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│              RESPONSE HEADER INJECTION                            │
│  - Add X-Correlation-ID: abc-123                               │
│  - Add X-Request-ID: xyz-789                                   │
│  - Add Content-Type: application/json                           │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                      HTTP RESPONSE (201 Created)                 │
│  Headers:                                                       │
│    X-Correlation-ID: abc-123                                   │
│    X-Request-ID: xyz-789                                       │
│                                                                 │
│  Body:                                                          │
│  {                                                              │
│    "status": "success",                                         │
│    "data": {                                                    │
│      "id": "job-123",                                           │
│      "job_type": "model_training",                             │
│      "status": "pending",                                       │
│      "priority": 5,                                             │
│      "created_at": "2026-05-20T10:30:45Z",                     │
│      ...                                                        │
│    },                                                           │
│    "correlation_id": "abc-123",                                │
│    "timestamp": "2026-05-20T10:30:45Z"                         │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
```

## Layer Dependencies

```
┌─────────────────────────────┐
│  PRESENTATION LAYER         │
│  (HTTP, Routes, Swagger)    │
│                             │
│  - routes/v1/jobs/          │
│  - middleware/              │
│  - dto/                     │
└────────────────┬────────────┘
                 │
                 │ depends on
                 ▼
┌─────────────────────────────┐
│  APPLICATION LAYER          │
│  (Use Cases, Orchestration) │
│                             │
│  - use_cases/job/           │
│  - dto/                     │
│  - exceptions/              │
└────────────────┬────────────┘
                 │
                 │ depends on
                 ▼
┌─────────────────────────────┐
│  DOMAIN LAYER               │
│  (Business Logic)           │
│                             │
│  - entities/                │
│  - repositories/            │
│  - value_objects/           │
└────────────────┬────────────┘
                 │
                 │ depends on
                 ▼
┌─────────────────────────────┐
│  INFRASTRUCTURE LAYER       │
│  (MongoDB, RabbitMQ, etc.)  │
│                             │
│  - persistence/mongodb/     │
│  - messaging/rabbitmq/      │
│  - cache/redis/             │
└─────────────────────────────┘

No backflow: Infrastructure ≠> Domain ≠> Application ≠> Presentation
```

## Component Interactions

```
REQUEST HANDLER
(Routes Controller)
    │
    ├─── Resolves ──→ USE CASE
    │                 │
    │                 ├─── Uses ──→ DOMAIN ENTITY
    │                 │             │
    │                 │             └─── Validates Invariants
    │                 │
    │                 ├─── Calls ──→ REPOSITORY INTERFACE
    │                 │             │
    │                 │             └─── Implemented by
    │                 │                   MONGODB REPOSITORY
    │                 │
    │                 └─── Publishes ──→ EVENTS
    │
    ├─── Reads ──→ PYDANTIC SCHEMA
    │             (Request validation)
    │
    ├─── Writes to ──→ RESPONSE ENVELOPE
    │                 (DataResponse, ErrorResponse)
    │
    └─── Has access to ──→ FLASK g
                        (correlation_id, request_id, user_id)
```

## Example: Create Job Request Flow

### Step 1: Validation

```
POST /api/v1/jobs
{
  "job_type": "model_training",
  "input_data": {"model": "bert"},
  "priority": 5
}
        │
        ▼
@validate_request_schema(CreateJobRequest)
        │
        ├─ job_type: str ✓
        ├─ input_data: dict ✓
        ├─ priority: 1-10 ✓
        │
        └─► request.validated_data = CreateJobRequest(...)
```

### Step 2: Use Case Execution

```
use_case = CreateJobUseCase(repository)
        │
        ▼
use_case.execute(request.validated_data)
        │
        ├─ Create Job entity
        │  job = Job(
        │    id="job-123",
        │    job_type="model_training",
        │    status="pending",
        │    created_at=now()
        │  )
        │
        ├─ Save to repository
        │  saved = repository.save(job)
        │
        └─ Return saved job
```

### Step 3: Response Formatting

```
Response Mapper
        │
        ├─ Format data
        │  {
        │    "id": "job-123",
        │    "status": "pending",
        │    "job_type": "model_training"
        │  }
        │
        ├─ Add envelope
        │  {
        │    "status": "success",
        │    "data": { ... },
        │    "correlation_id": "abc-123",
        │    "timestamp": "2026-05-20T10:30:45Z"
        │  }
        │
        └─ Return 201 Created
```

## Error Handling Flow

```
Try Execute
    │
    ├─► ValidationError (400)
    │   {
    │     "error": {
    │       "code": "VALIDATION_ERROR",
    │       "message": "Invalid job type",
    │       "details": [...]
    │     }
    │   }
    │
    ├─► NotFoundError (404)
    │   {
    │     "error": {
    │       "code": "NOT_FOUND",
    │       "message": "Job not found"
    │     }
    │   }
    │
    ├─► ConflictError (409)
    │   {
    │     "error": {
    │       "code": "CONFLICT",
    │       "message": "Job already exists"
    │     }
    │   }
    │
    ├─► Unexpected Exception (500)
    │   {
    │     "error": {
    │       "code": "INTERNAL_SERVER_ERROR",
    │       "message": "An unexpected error occurred"
    │     }
    │   }
    │
    └─► All responses include:
        - correlation_id (for tracing)
        - timestamp (request time)
        - X-Correlation-ID header
```

## File Organization

```
api_service/src/
│
├── presentation/                    ← HTTP Layer
│   ├── app.py                       (Factory, blueprint registration)
│   ├── config.py                    (Service configuration)
│   ├── context.py                   (Request context, correlation IDs)
│   ├── logger.py                    (Structured logging)
│   ├── container.py                 (Dependency injection)
│   ├── errors.py                    (API error classes)
│   │
│   ├── middleware/                  (Request processing)
│   │   ├── validation.py           (Schema validation)
│   │   ├── error_handler.py        (Error formatting)
│   │   └── correlation.py          (Correlation ID injection)
│   │
│   ├── routes/v1/                   (API endpoints)
│   │   ├── base.py                 (BaseBlueprint)
│   │   ├── health.py               (Health checks)
│   │   ├── jobs/
│   │   │   ├── controller.py       (Route handlers)
│   │   │   ├── schemas.py          (Request schemas)
│   │   │   └── responses.py        (Response models)
│   │   ├── users/
│   │   │   ├── controller.py
│   │   │   ├── schemas.py
│   │   │   └── responses.py
│   │   └── v2/                     (Future API versions)
│   │
│   └── dto/                         (Data Transfer Objects)
│       ├── base.py                 (Response envelopes)
│       ├── common.py               (Common DTOs)
│       └── mappers.py              (Entity ↔ DTO)
│
├── application/                     ← Business Coordination
│   ├── use_cases/
│   │   ├── job/
│   │   │   ├── create_job.py      (CreateJobUseCase)
│   │   │   ├── list_jobs.py       (ListJobsUseCase)
│   │   │   ├── get_job.py         (GetJobUseCase)
│   │   │   └── cancel_job.py      (CancelJobUseCase)
│   │   └── user/
│   │
│   ├── dto/                        (Application DTOs)
│   │   ├── job_dto.py
│   │   └── user_dto.py
│   │
│   └── exceptions.py               (Application errors)
│
├── domain/                          ← Business Logic
│   ├── entities/
│   │   ├── job.py                 (Job entity)
│   │   └── user.py                (User entity)
│   │
│   ├── repositories/               (Data access contracts)
│   │   ├── job_repository.py      (IJobRepository interface)
│   │   └── user_repository.py     (IUserRepository interface)
│   │
│   └── value_objects/              (Immutable, self-validating)
│       └── job_status.py          (JobStatus, Priority)
│
└── infrastructure/                  ← External Systems
    ├── persistence/mongodb/
    │   ├── job_repository.py      (MongoJobRepository)
    │   └── user_repository.py     (MongoUserRepository)
    │
    ├── messaging/rabbitmq/
    │   └── event_publisher.py
    │
    └── cache/redis/
        └── cache_service.py
```

## Endpoint Examples

### Create Job
```
POST /api/v1/jobs
Content-Type: application/json

{
  "job_type": "model_training",
  "input_data": {
    "model": "bert-base",
    "learning_rate": 0.001
  },
  "priority": 5,
  "timeout_seconds": 3600
}

Response (201):
{
  "status": "success",
  "data": {
    "id": "job-123abc",
    "user_id": null,
    "job_type": "model_training",
    "status": "pending",
    "priority": 5,
    "created_at": "2026-05-20T10:30:45Z",
    "completed_at": null,
    "result": null,
    "error": null
  },
  "correlation_id": "abc123-def456",
  "timestamp": "2026-05-20T10:30:45Z"
}
```

### List Jobs
```
GET /api/v1/jobs?limit=25&offset=0&status=pending&sort_by=priority&sort_order=desc

Response (200):
{
  "status": "success",
  "data": [
    { "id": "job-1", "status": "pending", ... },
    { "id": "job-2", "status": "pending", ... }
  ],
  "pagination": {
    "limit": 25,
    "offset": 0,
    "total": 150,
    "page": 1,
    "pages": 6
  },
  "correlation_id": "abc123-def456",
  "timestamp": "2026-05-20T10:30:45Z"
}
```

### Error Response
```
POST /api/v1/jobs
{
  "job_type": "invalid_type",
  "input_data": {}
}

Response (400):
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request: 1 validation error(s)",
    "details": {
      "validation_errors": [
        {
          "field": "job_type",
          "message": "Invalid job type. Must be one of: ...",
          "type": "value_error"
        }
      ]
    }
  },
  "correlation_id": "abc123-def456",
  "timestamp": "2026-05-20T10:30:45Z"
}
```

## Correlation ID Tracing

```
Client Request
    │
    ├─ Header: X-Correlation-ID: abc123
    │
    ▼
API Service
    │
    ├─ Received correlation_id: abc123
    ├─ Log: correlation_id=abc123
    │
    ├─ Pass to Use Case: correlation_id=abc123
    │  │
    │  ├─ Create Job: correlation_id=abc123
    │  │
    │  ├─ Call Repository: correlation_id=abc123
    │  │  │
    │  │  └─ MongoDB save (with correlation_id metadata)
    │  │
    │  └─ Publish Event: correlation_id=abc123
    │     (RabbitMQ will route to other services)
    │
    └─ Response Header: X-Correlation-ID: abc123

Queue Service (receives event with correlation_id=abc123)
    │
    └─ Log: correlation_id=abc123
       (All logs across services have same correlation_id for tracing)

Other Services (process event with correlation_id=abc123)
    │
    └─ Log: correlation_id=abc123
       (Complete request trace across microservices)
```

## Security Model

```
Public Routes (No Auth)
├── GET /health
├── GET /health/ready
├── GET /health/live
└── POST /auth/login

Protected Routes (Auth + Authz)
├── POST /api/v1/jobs           (Requires authenticated user)
├── GET /api/v1/jobs            (Requires authenticated user)
├── GET /api/v1/jobs/{id}       (Requires authenticated user + ownership)
├── DELETE /api/v1/jobs/{id}    (Requires authenticated user + admin)
└── ...

Authentication Flow:
1. Client posts credentials to /auth/login
2. Server returns JWT token
3. Client includes token: Authorization: Bearer <token>
4. Middleware validates token → extracts user_id
5. Store user_id in g.user_id
6. Route handler checks ownership/permissions
7. Business logic includes user_id in operations
```

## Monitoring & Observability

```
Request Tracing
├── correlation_id: Unique per request
├── request_id: Unique per HTTP request
├── user_id: User making request
└── timestamp: Request time

Logging
├── Level: DEBUG, INFO, WARNING, ERROR
├── Format: JSON in production, text in development
├── Context: Includes correlation_id automatically
└── Log aggregation: ELK stack / Datadog / New Relic

Metrics
├── Request count: /health/metrics
├── Response time: Per endpoint
├── Error rate: Per status code
└── Latency percentiles: p50, p95, p99

Health Checks
├── GET /health: Is service running?
├── GET /health/ready: Can handle traffic?
├── GET /health/live: Kubernetes liveness
└── GET /health/metrics: Prometheus metrics
```

## Deployment Architecture

```
┌─────────────────────────────────────────┐
│         Load Balancer (nginx)           │
│                                         │
│  Directs traffic to healthy instances   │
└────────────────┬────────────────────────┘
                 │
        ┌────────┼────────┐
        │        │        │
        ▼        ▼        ▼
    ┌────┐  ┌────┐  ┌────┐
    │API │  │API │  │API │  (3 instances)
    │v1.0│  │v1.0│  │v1.0│
    └────┘  └────┘  └────┘
        │        │        │
        └────────┼────────┘
                 │
         ┌───────┴───────┐
         │               │
        ▼               ▼
    ┌─────────┐    ┌─────────┐
    │ MongoDB │    │RabbitMQ │
    │Cluster  │    │Cluster  │
    └─────────┘    └─────────┘

Per Instance:
├─ Health checked: /health/ready
├─ Metrics collected: /health/metrics
├─ Correlation IDs logged: All logs include correlation_id
└─ Requests traced: Request flow visible across microservices
```

## Summary

This architecture provides:

1. **Separation of Concerns**: Each layer has single responsibility
2. **Testability**: Easy to mock at layer boundaries
3. **Scalability**: Stateless design, horizontal scaling
4. **Observability**: Correlation IDs for distributed tracing
5. **Maintainability**: Clear patterns for adding new features
6. **Security**: Validation, error handling, JWT support
7. **Performance**: Caching, pagination, async-ready
8. **Reliability**: Error handling, retry logic, circuit breakers (future)

**Ready to extend** with new resources following the Jobs pattern.
