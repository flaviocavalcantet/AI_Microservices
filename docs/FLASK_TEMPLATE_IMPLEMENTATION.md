# Production-Grade Flask Application Template - Implementation Summary

## Overview

A complete, extensible Flask application template for the api_service that implements production-grade patterns:

- ✅ Factory Pattern for app creation with testability
- ✅ Blueprints for modular route organization
- ✅ Health checks (liveness and readiness probes)
- ✅ Structured logging with JSON formatting and correlation ID tracing
- ✅ Environment-aware configuration (dev/staging/prod/test)
- ✅ Dependency injection container for loose coupling
- ✅ Error handling middleware for consistent API responses
- ✅ Request context management with correlation IDs
- ✅ OpenAPI/Swagger for API documentation
- ✅ Cross-platform compatibility (Windows, Linux, Docker, Kubernetes)

## File Structure & Components

### Core Application Files

#### 1. `src/main.py` - Application Entry Point

**Purpose**: Bootstrap the Flask application with configuration validation

**Key Functions**:
- `validate_startup()`: Validates configuration at startup, fails fast
- `main()`: Creates app, logs startup info, runs Flask dev server

**Features**:
- Loads `.env` files before configuration
- Validates all required settings exist
- Logs startup information with context
- Handles startup errors gracefully

**Usage**:
```bash
python -m services.api_service.src.main
```

#### 2. `src/presentation/app.py` - Flask Factory

**Purpose**: Create and configure Flask application with all components

**Key Functions**:
- `create_app(config, container)`: Factory function creating configured Flask app
- `_register_blueprints(app)`: Register all route blueprints
- `_setup_swagger(app)`: Configure OpenAPI/Swagger documentation

**Factory Steps**:
1. Create Flask app instance
2. Load configuration object
3. Setup structured logging
4. Initialize dependency injection container
5. Setup request context management
6. Register error handlers
7. Configure CORS
8. Register blueprints
9. Setup Swagger/OpenAPI

**Example**:
```python
from services.api_service.src.presentation.app import create_app

app = create_app()
app.run(debug=True)
```

**Advantages**:
- Same factory used everywhere (dev, test, production)
- Flexible configuration per environment
- Easy to mock dependencies in tests
- Single point for app initialization
- Clean separation of concerns

#### 3. `src/config.py` - Environment Configuration

**Purpose**: Environment-specific configuration with validation

**Classes**:
- `Config`: Base with all common settings
- `DevelopmentConfig`: DEBUG=True, permissive CORS, DEBUG logging
- `StagingConfig`: Production-like, INFO logging, JSON format
- `ProductionConfig`: Strict validation, WARNING logging, Swagger disabled
- `TestingConfig`: In-memory databases, fast setup/teardown

**Key Settings**:
- `FLASK_ENV`: Environment name (development/staging/production/testing)
- `DEBUG`: Debug mode (only in development/testing)
- `LOG_LEVEL`: Logging level (DEBUG/INFO/WARNING/ERROR/CRITICAL)
- `LOG_FORMAT`: Log format (json for production, text for dev)
- `MONGODB_URI`: Database connection string
- `RABBITMQ_URL`: Message broker connection
- `REDIS_URL`: Cache connection
- `JWT_SECRET_KEY`: Token signing key (validated in production)
- `CORS_ALLOWED_ORIGINS`: Allowed CORS origins (permissive in dev, strict in prod)

**Validation**:
- Production validates MONGODB_URI not localhost
- Production validates JWT_SECRET_KEY >= 32 characters
- Production validates JWT_SECRET_KEY set and not using dev value

**Usage**:
```python
from services.api_service.src.config import get_config

config = get_config()  # Auto-detects FLASK_ENV
config = get_config("production")  # Force environment
```

#### 4. `src/logger.py` - Structured Logging

**Purpose**: JSON-formatted logging with correlation ID support

**Classes**:
- `JSONFormatter`: Converts log records to JSON for aggregation systems
- `TextFormatter`: Human-readable format for development
- `ContextAwareAdapter`: Injects Flask context (correlation_id, request_id) into logs

**Key Functions**:
- `setup_logging(log_level, log_format)`: Configure root and Flask loggers
- `get_logger(name)`: Get logger with context injection

**Features**:
- JSON format with timestamp, level, logger, message
- Adds exception traceback in JSON
- Injects correlation_id, request_id, user_id from Flask context
- Supports extra fields for custom context
- Text format for development with optional prefixes
- Suppresses noisy libraries (werkzeug, pymongo)

**Example**:
```python
from services.api_service.src.logger import setup_logging, get_logger

# Setup at app creation
setup_logging(log_level="INFO", log_format="json")

# Get logger with context injection
logger = get_logger(__name__)

# Logs automatically include correlation_id from Flask g
logger.info("User created", extra={"user_id": "123"})

# Output:
# {
#   "timestamp": "2026-05-18T10:30:45.123Z",
#   "level": "INFO",
#   "logger": "services.api_service.src.routes.users",
#   "message": "User created",
#   "correlation_id": "abc-123-def",
#   "request_id": "xyz-789",
#   "user_id": "123"
# }
```

#### 5. `src/container.py` - Dependency Injection

**Purpose**: Service container for dependency injection

**Classes**:
- `ServiceContainer`: Manages service registration and resolution
  - `register(name, factory, singleton)`: Register service factory
  - `register_instance(name, instance)`: Register pre-created instance
  - `resolve(name)`: Get service instance
  - `has_service(name)`: Check if service registered
  - `clear()`: Clear all services (for testing)

**Module Functions**:
- `get_container()`: Get global container instance
- `init_container(container)`: Set global container

**Features**:
- Singleton services (created once, reused)
- Transient services (created each time)
- Pre-created instances
- Lazy initialization
- Supports testing with mocked containers

**Example**:
```python
from services.api_service.src.container import get_container

# Register services (in factory)
container.register("database", create_database, singleton=True)
container.register("logger", get_logger, singleton=False)
container.register_instance("config", config)

# Resolve in routes
container = get_container()
db = container.resolve("database")
logger = container.resolve("logger")(__name__)

# In tests - replace with mocks
mock_container = ServiceContainer()
mock_container.register_instance("database", MockDatabase())
init_container(mock_container)
```

#### 6. `src/context.py` - Request Context Management

**Purpose**: Manage request context with correlation IDs for tracing

**Classes**:
- `RequestContextManager`: Flask before/after/teardown request handlers

**Module Functions**:
- `get_correlation_id()`: Get correlation ID (traces across services)
- `get_request_id()`: Get request ID (unique per request)
- `get_user_id()`: Get user ID from token

**Features**:
- Generates/retrieves correlation IDs across microservices
- Generates unique request IDs per request
- Extracts user ID from JWT token (when auth implemented)
- Adds X-Correlation-ID and X-Request-ID to response headers
- Stores in Flask g context (request-scoped)
- Integrated with structured logging

**Setup** (automatic in factory):
```python
RequestContextManager.setup_request_context(app)
```

**Usage**:
```python
from services.api_service.src.context import (
    get_correlation_id,
    get_request_id,
    get_user_id
)

@app.route("/jobs")
def get_jobs():
    correlation_id = get_correlation_id()  # abc-123-def
    request_id = get_request_id()          # xyz-789
    user_id = get_user_id()                # user-456
    
    logger.info("Getting jobs")
    # Automatically includes correlation_id
    
    return {"jobs": []}

# Response headers:
# X-Correlation-ID: abc-123-def
# X-Request-ID: xyz-789
```

**Tracing**:
- Client requests with correlation ID
- Service A receives, logs with correlation ID
- Service A calls Service B, passes correlation ID
- Service B logs with same correlation ID
- Easy to trace request through all services

#### 7. `src/errors.py` - Error Handling

**Purpose**: Consistent API error responses

**Exception Classes**:
- `APIError`: Base exception (400)
- `ValidationError`: Validation failed (400)
- `UnauthorizedError`: Authentication required (401)
- `ForbiddenError`: Insufficient permissions (403)
- `NotFoundError`: Resource not found (404)
- `ConflictError`: Resource already exists (409)
- `RateLimitError`: Too many requests (429)
- `ServiceUnavailableError`: External service down (503)

**Key Functions**:
- `register_error_handlers(app)`: Register Flask error handlers

**Features**:
- Automatic HTTP status code mapping
- Machine-readable error codes
- Human-readable error messages
- Optional error details
- JSON serialization
- Logs errors with context
- Handles unexpected exceptions

**Example**:
```python
from services.api_service.src.errors import (
    ValidationError,
    NotFoundError,
    ConflictError
)

@app.route("/users", methods=["POST"])
def create_user():
    # Validation error
    if not request.json.get("email"):
        raise ValidationError(
            "Email is required",
            details={"field": "email"}
        )
    
    # Conflict error
    if user_exists(email):
        raise ConflictError(f"User {email} already exists")
    
    # Not found error
    if not department_exists(dept_id):
        raise NotFoundError("Department")
    
    return {"user": new_user}, 201

# Response:
# {
#   "status": "error",
#   "error": {
#     "code": "VALIDATION_ERROR",
#     "message": "Email is required",
#     "details": {"field": "email"}
#   }
# }
# Status: 400
```

#### 8. `src/presentation/routes/health.py` - Health Checks

**Purpose**: Health check endpoints for orchestration

**Endpoints**:
- `GET /health` - Liveness check (is service running?)
- `GET /health/ready` - Readiness check (is service ready?)
- `GET /health/live` - Kubernetes liveness probe
- `GET /health/metrics` - Metrics (TODO: implement)

**Liveness Check** (`GET /health`):
- Lightweight check
- No external dependencies
- Used by load balancers
- Returns 200 if running, 503 if crashed

**Readiness Check** (`GET /health/ready`):
- Thorough check
- Verifies dependencies (database, cache, message queue)
- Returns 200 if ready, 503 if not
- Used by orchestrators for traffic routing

**Examples**:
```bash
# Liveness
$ curl http://localhost:5000/health
{
  "status": "healthy",
  "service": "api_service",
  "timestamp": "2026-05-18T10:30:45Z"
}

# Readiness
$ curl http://localhost:5000/health/ready
{
  "status": "ready",
  "service": "api_service",
  "dependencies": {
    "database": "healthy",
    "cache": "healthy",
    "message_queue": "healthy"
  },
  "timestamp": "2026-05-18T10:30:45Z"
}

# Not ready
$ curl http://localhost:5000/health/ready
{
  "status": "not_ready",
  "dependencies": {
    "database": "unhealthy",
    "cache": "healthy",
    "message_queue": "healthy"
  },
  "timestamp": "2026-05-18T10:30:45Z"
}
```

### Route Blueprints

#### `src/presentation/routes/` - Route Organization

**Health Blueprint** (`health.py`):
- Already implemented
- 4 endpoints for monitoring

**User Blueprint** (TODO):
- Create `users.py`
- GET /api/v1/users - List users
- POST /api/v1/users - Create user
- GET /api/v1/users/<id> - Get user
- PUT /api/v1/users/<id> - Update user
- DELETE /api/v1/users/<id> - Delete user

**Job Blueprint** (TODO):
- Create `jobs.py`
- GET /api/v1/jobs - List jobs
- POST /api/v1/jobs - Create job
- GET /api/v1/jobs/<id> - Get job status
- PUT /api/v1/jobs/<id>/cancel - Cancel job

**Pattern for New Blueprint**:
```python
from flask import Blueprint, request, jsonify
from services.api_service.src.logger import get_logger
from services.api_service.src.container import get_container

logger = get_logger(__name__)

items_bp = Blueprint("items", __name__, url_prefix="/api/v1/items")

@items_bp.route("", methods=["GET"])
def list_items():
    """List all items"""
    container = get_container()
    service = container.resolve("item_service")
    return {"items": service.get_all()}

@items_bp.route("", methods=["POST"])
def create_item():
    """Create new item"""
    container = get_container()
    service = container.resolve("item_service")
    item = service.create(request.json)
    logger.info(f"Item created: {item.id}")
    return {"item": item.to_dict()}, 201
```

### Infrastructure Directories

#### `src/domain/` - Pure Domain Logic

**No framework dependencies** - Can be used standalone

**Subdirectories**:
- `entities/`: Domain entities (Job, User, Request)
- `repositories/`: Repository interfaces (no implementation)

**Example Entity**:
```python
# src/domain/entities/job.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Job:
    id: str
    user_id: str
    job_type: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    
    def can_cancel(self) -> bool:
        return self.status in ["pending", "running"]
    
    def mark_completed(self):
        self.status = "completed"
        self.completed_at = datetime.utcnow()
```

**Example Repository Interface**:
```python
# src/domain/repositories/job_repository.py
from abc import ABC, abstractmethod

class IJobRepository(ABC):
    @abstractmethod
    def save(self, job: Job) -> Job:
        pass
    
    @abstractmethod
    def find_by_id(self, job_id: str) -> Optional[Job]:
        pass
    
    @abstractmethod
    def find_all(self) -> List[Job]:
        pass
```

#### `src/application/` - Business Logic Orchestration

**Subdirectories**:
- `use_cases/`: Business logic services
- `dto/`: Data transfer objects
- `exceptions/`: Application-level exceptions

**Example Use Case**:
```python
# src/application/use_cases/job_service.py
from services.api_service.src.logger import get_logger

logger = get_logger(__name__)

class CreateJobUseCase:
    def __init__(self, repository):
        self.repository = repository
    
    def execute(self, job_type: str, input_data: dict) -> Job:
        # Validate input
        if not job_type:
            raise ValueError("job_type required")
        
        # Create domain entity
        job = Job(
            id=generate_id(),
            user_id=current_user.id,
            job_type=job_type,
            status="pending",
            created_at=datetime.utcnow()
        )
        
        # Save to repository
        saved_job = self.repository.save(job)
        
        # Publish event
        event_bus.publish(JobCreatedEvent(job.id, job.user_id))
        
        logger.info(f"Job created: {job.id}")
        return saved_job
```

#### `src/infrastructure/` - External Services

**Subdirectories**:
- `persistence/`: Database implementations
- `messaging/`: Message broker implementations

**Example MongoDB Repository**:
```python
# src/infrastructure/persistence/job_repository.py
from pymongo import MongoClient
from services.api_service.src.domain.repositories.job_repository import IJobRepository

class MongoJobRepository(IJobRepository):
    def __init__(self, connection_string: str):
        self.client = MongoClient(connection_string)
        self.db = self.client.ai_platform
        self.collection = self.db.jobs
    
    def save(self, job: Job) -> Job:
        self.collection.insert_one(job.to_dict())
        return job
    
    def find_by_id(self, job_id: str) -> Optional[Job]:
        doc = self.collection.find_one({"_id": job_id})
        return Job.from_dict(doc) if doc else None
```

## Running the Application

### Local Development

```bash
# 1. Copy environment
cp config/environments/.env.development .env

# 2. Install dependencies
pip install -r services/api_service/requirements.txt

# 3. Run
python -m services.api_service.src.main

# 4. Access
# API: http://localhost:5000/api/v1/...
# Swagger: http://localhost:5000/apidocs/
# Health: http://localhost:5000/health
```

### Docker

```bash
# Build
docker build -f services/api_service/Dockerfile -t api_service:latest .

# Run
docker run -p 5000:5000 \
  --env-file config/environments/.env.development \
  api_service:latest
```

### Docker Compose

```bash
docker-compose up api_service
docker-compose logs -f api_service
```

### Kubernetes

```bash
# Create secrets
kubectl create secret generic api_service-secrets \
  --from-literal=MONGODB_URI='...' \
  --from-literal=JWT_SECRET_KEY='...' \
  -n production

# Deploy
kubectl apply -f infrastructure/kubernetes/api_service.yaml

# Logs
kubectl logs -f deployment/api_service -n production

# Port forward
kubectl port-forward svc/api_service 5000:5000
```

## Design Patterns Used

### 1. Factory Pattern
- Single point for app creation
- Flexible configuration
- Easy testing

### 2. Dependency Injection
- Loose coupling between components
- Easy mocking in tests
- Single responsibility

### 3. Blueprints
- Modular route organization
- Scalable structure
- Clear separation

### 4. Repository Pattern
- Abstraction of data access
- Easy to swap implementations
- Testable with mocks

### 5. Adapter Pattern
- Context-aware logging
- Flask context injection
- Clean integration

### 6. Middleware Pattern
- Request/response processing
- Cross-cutting concerns
- Error handling

### 7. Strategy Pattern
- Configuration per environment
- Validation rules per environment
- Different logging strategies

## Security Considerations

### 1. Configuration Security
- Never commit secrets
- Use environment variables for secrets
- Validate at startup
- Production enforces strong JWT secrets

### 2. Error Handling
- Never expose internal details
- Log errors securely (no PII)
- Machine-readable error codes

### 3. CORS
- Permissive in development
- Restricted in staging
- Strict in production

### 4. Logging
- Never log sensitive data
- Use correlation IDs for tracing
- Remove PII before logging

### 5. Dependencies
- Validate inputs
- Use type hints
- Fail fast on errors

## Testing Strategy

### Unit Tests
```python
# Test configuration
def test_production_config_validates_mongodb():
    # Should raise if MONGODB_URI not set
    
# Test error handling
def test_validation_error_returns_400():
    # Should return 400 status
    
# Test logging
def test_logger_includes_correlation_id():
    # Should include correlation_id in JSON
```

### Integration Tests
```python
# Test with real Flask app
def test_health_check_endpoint():
    app = create_app(config=TestingConfig())
    client = app.test_client()
    response = client.get("/health")
    assert response.status_code == 200
```

### E2E Tests
```python
# Test with Docker or Kubernetes
def test_api_with_docker():
    # Start container
    # Make requests
    # Verify responses
```

## Extensibility Points

The template is designed to be extended with:

- **Authentication**: JWT middleware, login routes
- **Authorization**: Permission checks, role-based access
- **Validation**: Pydantic models, input validation
- **Caching**: Redis integration, cache decorators
- **Database**: MongoDB repositories, migrations
- **Events**: Event publishing/subscription
- **Tracing**: OpenTelemetry integration
- **Monitoring**: Prometheus metrics
- **Rate Limiting**: Flask-Limiter
- **Documentation**: Expanded Swagger docs

Each can be added without modifying core factory.

## Performance Considerations

### 1. Caching
- Use singleton services (already done)
- Cache expensive operations
- Use Redis for distributed cache

### 2. Logging
- JSON format is structured (good for aggregation)
- Can be slow for high volume - use async
- Consider log sampling in production

### 3. Blueprints
- Each blueprint is registered once
- Route matching is O(1) in Flask
- Can scale to hundreds of routes

### 4. Database
- Connection pooling via MongoClient
- Implement repository caching
- Index commonly queried fields

### 5. Deployment
- Run multiple workers with Gunicorn
- Use Kubernetes for auto-scaling
- Monitor CPU/memory usage

## Troubleshooting

### Won't Start
- Check environment variables: `env | grep FLASK`
- Check configuration: `python -c "from services.api_service.src.config import get_config; print(get_config())"`
- Check logs: `LOG_LEVEL=DEBUG python -m services.api_service.src.main`

### Health Check Fails
- Check dependencies are running: `docker-compose ps`
- Verify connection strings: `echo $MONGODB_URI $RABBITMQ_URL`
- Test manually: `mongo --uri "$MONGODB_URI"`

### Slow Startup
- Check app initialization time
- Profile with: `python -m cProfile -s cumtime -m services.api_service.src.main`
- May be database connection - use connection pooling

### Errors Not Caught
- Ensure error handler registered: check app factory
- Verify exception type matches handler
- Check exception hierarchy

## Related Documentation

- [Configuration Management](../CONFIGURATION.md)
- [Environment Configuration Guide](../ENVIRONMENT_CONFIGURATION.md)
- [Clean Architecture](../CLEAN_ARCHITECTURE.md)
- [Event Contracts](../EVENT_CONTRACTS.md)
- [Testing Strategy](../TESTING.md)
- [Database Schema](../DATABASE_SCHEMA.md)
- [Deployment Guide](../DEPLOYMENT.md)
- [API Specification](../API_SPECIFICATION.md)
