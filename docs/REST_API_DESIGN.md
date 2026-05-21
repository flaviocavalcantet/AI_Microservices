# REST API Module Structure Design

## Overview

Production-grade REST API module structure for api-service implementing:
- Clean Architecture with framework-independent domain logic
- API versioning (v1, v2, etc.)
- Clear separation: Routes → Controllers → Services → Domain
- Request/response validation with schemas
- Middleware for cross-cutting concerns
- Health checks and error handling
- Correlation ID tracing
- Structured responses

## Folder Structure

```
services/api-service/src/
├── presentation/
│   ├── __init__.py
│   ├── app.py                          # Flask factory
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py                     # Authentication (TODO)
│   │   ├── validation.py               # Request validation
│   │   ├── error_handler.py            # Error handling
│   │   └── correlation.py              # Correlation ID injection
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # BaseBlueprint class
│   │   │   ├── health.py               # Health check routes
│   │   │   ├── jobs/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── controller.py       # Route handlers
│   │   │   │   ├── schemas.py          # Request/response schemas
│   │   │   │   └── responses.py        # Response models
│   │   │   ├── users/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── controller.py
│   │   │   │   ├── schemas.py
│   │   │   │   └── responses.py
│   │   │   └── requests/
│   │   │       ├── __init__.py
│   │   │       ├── controller.py
│   │   │       ├── schemas.py
│   │   │       └── responses.py
│   │   └── v2/                         # (Future API version)
│   │       ├── __init__.py
│   │       └── ...
│   ├── dto/
│   │   ├── __init__.py
│   │   ├── base.py                     # BaseDTO, BaseResponse
│   │   ├── common.py                   # Pagination, errors
│   │   └── mappers.py                  # Domain ↔ DTO mapping
│   └── responses.py                    # Response envelope
├── application/
│   ├── __init__.py
│   ├── use_cases/
│   │   ├── __init__.py
│   │   ├── job/
│   │   │   ├── __init__.py
│   │   │   ├── create_job.py           # Use case
│   │   │   ├── get_job.py
│   │   │   ├── list_jobs.py
│   │   │   └── cancel_job.py
│   │   ├── user/
│   │   │   ├── __init__.py
│   │   │   └── ...
│   │   └── request/
│   │       ├── __init__.py
│   │       └── ...
│   ├── dto/
│   │   ├── __init__.py
│   │   ├── job_dto.py                  # Job DTOs (for responses)
│   │   ├── user_dto.py
│   │   └── request_dto.py
│   └── exceptions.py                   # Application exceptions
├── domain/
│   ├── __init__.py
│   ├── entities/
│   │   ├── __init__.py
│   │   ├── job.py                      # Job entity
│   │   ├── user.py
│   │   ├── request.py
│   │   └── value_objects/
│   │       ├── __init__.py
│   │       ├── job_status.py
│   │       └── ...
│   └── repositories/
│       ├── __init__.py
│       ├── job_repository.py           # Interfaces only
│       ├── user_repository.py
│       └── request_repository.py
├── infrastructure/
│   ├── __init__.py
│   ├── persistence/
│   │   ├── __init__.py
│   │   ├── mongodb/
│   │   │   ├── __init__.py
│   │   │   ├── job_repository.py       # MongoDB implementation
│   │   │   ├── user_repository.py
│   │   │   └── base_repository.py
│   │   └── redis/
│   │       ├── __init__.py
│   │       └── cache.py
│   └── messaging/
│       ├── __init__.py
│       ├── event_publisher.py          # RabbitMQ events
│       └── event_handlers.py
├── config.py                           # Configuration
├── logger.py                           # Structured logging
├── container.py                        # Dependency injection
├── context.py                          # Request context
├── errors.py                           # Error classes
└── main.py                             # Entry point
```

## Component Responsibilities

### Presentation Layer

#### `presentation/routes/v1/base.py`
**Base Blueprint Class**

Provides common functionality for all blueprints:
- Logging context injection
- Common response formatting
- Error handling
- Dependency injection

```python
class BaseBlueprint:
    """Base class for all API blueprints"""
    
    def __init__(self, name, url_prefix):
        self.bp = Blueprint(name, __name__, url_prefix=url_prefix)
        self.logger = get_logger(__name__)
    
    def get_container(self):
        return get_container()
    
    def register(self, app):
        app.register_blueprint(self.bp)
```

#### `presentation/routes/v1/health.py`
**Health Check Routes**

Liveness and readiness probes:
- `/health` - Service running?
- `/health/ready` - Ready for traffic?
- `/health/live` - Kubernetes liveness
- `/health/metrics` - Metrics placeholder

#### `presentation/routes/v1/jobs/controller.py`
**Route Handlers (Controllers)**

Flask route handlers calling use cases:
- Parse HTTP request
- Call service/use case
- Return formatted response
- No business logic here

```python
@jobs_bp.route('', methods=['POST'])
def create_job():
    """Create new job (POST /api/v1/jobs)"""
    # 1. Parse and validate request
    # 2. Get use case from container
    # 3. Call use case
    # 4. Return response
```

#### `presentation/routes/v1/jobs/schemas.py`
**Request/Response Schemas**

Pydantic models for validation:
- `CreateJobRequest` - Input validation
- `UpdateJobRequest` - Input validation
- Response models are in `responses.py`

```python
class CreateJobRequest(BaseModel):
    job_type: str = Field(..., min_length=1)
    input_data: dict
    priority: int = Field(default=5, ge=1, le=10)
```

#### `presentation/routes/v1/jobs/responses.py`
**Response Models**

Data structures for API responses:
- `JobResponse` - Job details
- `JobListResponse` - Paginated list

```python
class JobResponse(BaseResponse):
    id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
```

#### `presentation/dto/base.py`
**Base DTO Classes**

Common base classes:
- `BaseDTO` - Request DTOs
- `BaseResponse` - Response DTOs
- `BaseListResponse` - Paginated responses

```python
class BaseResponse(BaseModel):
    """Base for all API responses"""
    status: str = "success"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None
```

#### `presentation/middleware/`
**Middleware Components**

- `validation.py` - Request schema validation
- `error_handler.py` - Error handling and formatting
- `correlation.py` - Correlation ID injection
- `auth.py` - Authentication (future)

### Application Layer

#### `application/use_cases/job/create_job.py`
**Use Cases**

Business logic orchestration:
- Coordinate domain logic
- Call repositories
- Publish events
- No HTTP concerns

```python
class CreateJobUseCase:
    """Create new job use case"""
    
    def __init__(self, repository, event_publisher):
        self.repository = repository
        self.event_publisher = event_publisher
    
    def execute(self, input_dto: CreateJobDTO) -> Job:
        # 1. Create domain entity
        # 2. Validate business rules
        # 3. Save to repository
        # 4. Publish event
        # 5. Return entity
```

#### `application/dto/`
**Application DTOs**

Data transfer objects for use cases:
- `CreateJobDTO` - Input to create use case
- `JobDTO` - Output from use case

Framework-independent, mirrors domain entities.

#### `application/exceptions.py`
**Application Exceptions**

Application-specific exceptions:
- `JobNotFoundError`
- `InvalidJobStatusError`
- `InsufficientPermissionsError`

Maps to domain exceptions.

### Domain Layer

#### `domain/entities/job.py`
**Domain Entities**

Pure business logic (framework-independent):
- Job entity with invariants
- Domain methods (can_cancel, mark_complete)
- No ORM decorators
- No HTTP awareness

```python
class Job:
    def __init__(self, id, user_id, job_type, ...):
        self.id = id
        self.user_id = user_id
        self.job_type = job_type
        self.status = JobStatus.PENDING
    
    def can_cancel(self) -> bool:
        """Domain rule: can only cancel if pending or running"""
        return self.status in [JobStatus.PENDING, JobStatus.RUNNING]
    
    def mark_completed(self, result):
        """Domain rule: mark completed with validation"""
        if not self.can_complete():
            raise DomainError("Cannot complete job")
        self.status = JobStatus.COMPLETED
        self.result = result
```

#### `domain/repositories/job_repository.py`
**Repository Interfaces**

Contracts for data access (no implementation):
- `IJobRepository` interface
- `find_by_id(id) -> Job`
- `save(job) -> Job`
- `find_all() -> List[Job]`

```python
class IJobRepository(ABC):
    @abstractmethod
    def save(self, job: Job) -> Job:
        pass
    
    @abstractmethod
    def find_by_id(self, job_id: str) -> Optional[Job]:
        pass
```

### Infrastructure Layer

#### `infrastructure/persistence/mongodb/job_repository.py`
**Repository Implementation**

Implements repository interface with MongoDB:
- Translate domain entities ↔ MongoDB documents
- Handle queries
- Connection pooling

```python
class MongoJobRepository(IJobRepository):
    def __init__(self, db):
        self.db = db
        self.collection = db.jobs
    
    def save(self, job: Job) -> Job:
        doc = JobMapper.to_document(job)
        self.collection.insert_one(doc)
        return job
```

## Dependency Flow

```
HTTP Request
    ↓
[Middleware] - Validation, correlation ID, auth
    ↓
[Routes/Controller] - Parse HTTP, call use case
    ↓
[Application Layer] - Use cases, orchestrate domain logic
    ↓
[Domain Layer] - Business logic, validation
    ↓
[Repository Interface] - Abstract data access
    ↓
[Infrastructure] - MongoDB, RabbitMQ implementation
    ↓
Response (JSON)
```

**Request Flow**:
```
POST /api/v1/jobs
    ↓ Middleware validates schema
    ↓ Controller gets use case from container
    ↓ Controller calls create_job_use_case.execute(dto)
    ↓ Use case creates domain entity
    ↓ Use case calls repository.save(job)
    ↓ Repository implements via MongoDB
    ↓ Use case publishes JobCreatedEvent
    ↓ Controller returns JobResponse
    ↓ Middleware formats as JSON
    ↓ Client receives response
```

**No Backflow**: Lower layers don't know about higher layers
- Infrastructure doesn't know about Flask
- Domain doesn't import application
- Application doesn't import presentation

## Naming Conventions

### Files & Directories

| Type | Pattern | Example |
|------|---------|---------|
| Blueprint | `{resource}_bp` | `jobs_bp` |
| Controller | `{Resource}Controller` | `JobController` |
| Use Case | `{Action}{Resource}UseCase` | `CreateJobUseCase` |
| Entity | `{Resource}` | `Job` |
| Repository Interface | `I{Resource}Repository` | `IJobRepository` |
| Repository Impl | `Mongo{Resource}Repository` | `MongoJobRepository` |
| Request Schema | `{Action}{Resource}Request` | `CreateJobRequest` |
| Response Schema | `{Resource}Response` | `JobResponse` |
| DTO | `{Resource}DTO` | `JobDTO` |
| Exception | `{Action}{Resource}Error` or `{Resource}NotFoundError` | `JobNotFoundError` |
| Middleware | `{concern}_middleware` | `validation_middleware` |

### URL Patterns

| Method | Pattern | Example |
|--------|---------|---------|
| List | `GET /api/v{n}/{resources}` | `GET /api/v1/jobs` |
| Create | `POST /api/v{n}/{resources}` | `POST /api/v1/jobs` |
| Get | `GET /api/v{n}/{resources}/{id}` | `GET /api/v1/jobs/123` |
| Update | `PUT /api/v{n}/{resources}/{id}` | `PUT /api/v1/jobs/123` |
| Delete | `DELETE /api/v{n}/{resources}/{id}` | `DELETE /api/v1/jobs/123` |
| Action | `POST /api/v{n}/{resources}/{id}/{action}` | `POST /api/v1/jobs/123/cancel` |

### Classes & Functions

| Type | Pattern | Example |
|------|---------|---------|
| Blueprint Class | `{Resource}Blueprint` | `JobBlueprint` |
| Factory | `create_{resource}` | `create_job_use_case` |
| Handler | `handle_{action}_{resource}` | `handle_create_job` |
| Validator | `validate_{field}` | `validate_job_type` |
| Mapper | `{Source}To{Target}Mapper` | `JobToResponseMapper` |
| Decorator | `require_{permission}` | `require_admin` |

## API Versioning Strategy

### Version Directories

```
routes/
├── v1/              # Current stable
│   ├── jobs/
│   ├── users/
│   └── __init__.py
├── v2/              # Future version (when needed)
│   ├── jobs/
│   ├── users/
│   └── __init__.py
```

### Backward Compatibility

- v1 remains stable for existing clients
- v2 adds new features without breaking v1
- Deprecation warnings added to old versions
- Support timeline: maintain v(n-1) + current version

### Version in Factory

```python
def create_app():
    app = Flask(__name__)
    
    # Register v1 blueprints
    from routes.v1.jobs import jobs_bp
    app.register_blueprint(jobs_bp)
    
    # Register v2 blueprints (in future)
    # from routes.v2.jobs import jobs_bp_v2
    # app.register_blueprint(jobs_bp_v2)
    
    return app
```

## Request/Response Pattern

### Request

```python
# Client sends
POST /api/v1/jobs
{
  "job_type": "training",
  "input_data": {"model": "bert"},
  "priority": 8
}

# Presentation layer
@jobs_bp.route('', methods=['POST'])
def create_job():
    schema = CreateJobRequest(**request.json)  # Validates
    use_case = get_container().resolve('create_job_use_case')
    job = use_case.execute(CreateJobDTO.from_schema(schema))
    return jsonify(JobResponse.from_entity(job)), 201
```

### Response

```python
# Server returns
{
  "status": "success",
  "timestamp": "2026-05-20T10:30:45Z",
  "correlation_id": "abc-123-def",
  "data": {
    "id": "job-456",
    "status": "pending",
    "created_at": "2026-05-20T10:30:45Z",
    "completed_at": null
  }
}
```

### Error Response

```json
{
  "status": "error",
  "timestamp": "2026-05-20T10:30:45Z",
  "correlation_id": "abc-123-def",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid job type",
    "details": {
      "field": "job_type",
      "expected": "string",
      "received": "number"
    }
  }
}
```

## Middleware Organization

### Middleware Stack

```
Request
  ↓ [Correlation ID] - Inject tracking IDs
  ↓ [Request Validation] - Validate schema
  ↓ [Authentication] - TODO: JWT validation
  ↓ [Authorization] - TODO: Permission checks
  ↓ [Error Handler] - Catch exceptions
  ↓ Route Handler
  ↓ [Response Formatter] - Format response
Response
```

### Implementation

```python
# presentation/middleware/correlation.py
def inject_correlation_id(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        g.correlation_id = request.headers.get('X-Correlation-ID', generate_id())
        return f(*args, **kwargs)
    return decorated

# presentation/middleware/validation.py
def validate_schema(schema_class):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            try:
                schema = schema_class(**request.json)
            except ValidationError as e:
                raise ValidationError(e.errors())
            return f(*args, **kwargs)
        return decorated
    return decorator

# presentation/app.py
app.before_request(inject_correlation_id)
app.before_request(validate_request_schema)
app.errorhandler(APIError)(handle_api_error)
```

## Health Check Endpoints

### Endpoints

```
GET /health              - Liveness check
GET /health/ready        - Readiness check (dependencies)
GET /health/live         - Kubernetes liveness probe
GET /health/metrics      - Metrics placeholder
```

### Response Examples

```json
// GET /health
{
  "status": "healthy",
  "service": "api-service",
  "version": "1.0.0",
  "timestamp": "2026-05-20T10:30:45Z"
}

// GET /health/ready
{
  "status": "ready",
  "service": "api-service",
  "dependencies": {
    "database": "healthy",
    "cache": "healthy",
    "message_queue": "healthy"
  },
  "timestamp": "2026-05-20T10:30:45Z"
}

// GET /health/live
{
  "status": "alive",
  "uptime_seconds": 3600,
  "timestamp": "2026-05-20T10:30:45Z"
}
```

## Error Handling Strategy

### Error Hierarchy

```
Exception
├── APIError
│   ├── ValidationError (400)
│   ├── UnauthorizedError (401)
│   ├── ForbiddenError (403)
│   ├── NotFoundError (404)
│   ├── ConflictError (409)
│   ├── RateLimitError (429)
│   └── ServiceUnavailableError (503)
├── DomainError (domain layer)
├── RepositoryError (infrastructure)
└── ExternalServiceError (infrastructure)
```

### Mapping

- Domain/Application exceptions → APIError
- Unexpected exceptions → 500 Internal Server Error
- Validation errors → 400 Bad Request
- Not found → 404 Not Found

### Global Error Handler

```python
@app.errorhandler(APIError)
def handle_api_error(error):
    logger.warning(f"API Error: {error.error_code}")
    response = error.to_dict()
    response['correlation_id'] = get_correlation_id()
    return jsonify(response), error.status_code

@app.errorhandler(Exception)
def handle_unexpected_error(error):
    logger.error(f"Unexpected error: {error}", exc_info=True)
    response = {
        "status": "error",
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "Internal server error",
        },
        "correlation_id": get_correlation_id()
    }
    return jsonify(response), 500
```

## Extensibility

### Adding New Resource

1. **Create Domain Entity** (`domain/entities/{resource}.py`)
   - Pure business logic
   - No framework dependencies

2. **Create Repository Interface** (`domain/repositories/{resource}_repository.py`)
   - Abstract data access

3. **Create Use Cases** (`application/use_cases/{resource}/`)
   - Orchestrate domain logic

4. **Create Repository Implementation** (`infrastructure/persistence/mongodb/{resource}_repository.py`)
   - MongoDB implementation

5. **Create Route Blueprint** (`presentation/routes/v1/{resource}/`)
   - Controller (routes)
   - Schemas (request validation)
   - Responses (response models)

6. **Register in Factory** (`presentation/app.py`)
   - Register blueprint
   - Register services in container

### Adding Middleware

1. Create middleware in `presentation/middleware/{concern}.py`
2. Register in factory with `app.before_request()` or `app.after_request()`
3. Add to docstring in factory for documentation

### Adding API Version

1. Create `presentation/routes/v2/` directory
2. Copy v1 routes as base
3. Modify as needed
4. Register v2 blueprints in factory
5. Keep v1 for backward compatibility

## Testing Strategy

### Unit Tests
- Test routes with mocked services
- Test schemas with invalid inputs
- Test mappers

```python
def test_create_job_route():
    with app.test_client() as client:
        response = client.post('/api/v1/jobs', json={...})
        assert response.status_code == 201
```

### Integration Tests
- Test with real services (mocked repositories)
- Test error handling
- Test middleware

```python
def test_create_job_with_invalid_type():
    with app.test_client() as client:
        response = client.post('/api/v1/jobs', json={"job_type": ""})
        assert response.status_code == 400
```

### End-to-End Tests
- Test with Docker
- Test complete request flow

## Best Practices

### 1. Controllers
- Parse HTTP, no business logic
- Call use case, return response
- Keep functions < 50 lines

### 2. Use Cases
- Orchestrate domain logic
- Call repositories
- Publish events
- Framework-independent

### 3. Domain
- Pure business logic
- No imports from presentation/application
- Testable in isolation

### 4. Repositories
- Abstract data access
- Interface in domain
- Implementation in infrastructure
- Easy to mock

### 5. DTOs
- Simple data containers
- Validation in schemas
- Mapping to/from domain

### 6. Responses
- Consistent envelope
- Include correlation ID
- Include timestamp
- Include status

## Security Considerations

1. **Input Validation**
   - Validate all requests with schemas
   - Use Pydantic for type safety

2. **Error Handling**
   - Never expose internal details
   - Log errors securely (no PII)

3. **CORS**
   - Configured in factory
   - Permissive in dev, strict in prod

4. **Authentication** (TODO)
   - JWT tokens
   - Middleware validation

5. **Authorization** (TODO)
   - Role-based access control
   - Per-action checks

## Performance Considerations

1. **Caching**
   - Use Redis via container
   - Cache frequent queries

2. **Pagination**
   - Implement for list endpoints
   - Default limit: 50, max: 1000

3. **Async** (Future)
   - Use async/await for I/O
   - Implement with Quart if needed

4. **Logging**
   - JSON format is structured
   - Can slow with high volume

## Related Documents

- [Clean Architecture](CLEAN_ARCHITECTURE.md)
- [Flask Application Template](FLASK_APPLICATION_TEMPLATE.md)
- [Configuration Management](CONFIGURATION.md)
- [Error Handling](errors.py documentation)
- [Testing Strategy](TESTING.md)
