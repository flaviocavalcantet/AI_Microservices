# Flask Application Template - API Service

This document describes the production-grade Flask application template for the api_service, including architecture, patterns, and usage.

## Overview

The Flask application template implements a maintainable, extensible architecture with:

- **Factory Pattern**: `create_app()` for flexible app creation with different configurations
- **Blueprints**: Modular route organization for separation of concerns
- **Health Checks**: Liveness and readiness probes for orchestration
- **Structured Logging**: JSON logging with correlation ID tracing
- **Environment-Aware Config**: Multi-environment configuration (dev, staging, prod, test)
- **Dependency Injection**: Service container for loose coupling
- **Error Handling**: Middleware for consistent API error responses
- **Request Context**: Correlation IDs for distributed tracing
- **OpenAPI/Swagger**: Automatic API documentation

## Project Structure

```
services/api_service/src/
├── presentation/              # HTTP layer (routes, middleware)
│   ├── app.py                # Flask application factory
│   ├── __init__.py
│   ├── middleware/           # Middleware (auth, validation, etc.)
│   │   └── __init__.py
│   └── routes/               # API route blueprints
│       ├── health.py        # Health check endpoints
│       └── __init__.py
├── application/              # Application layer (use cases, DTOs)
│   ├── use_cases/           # Business logic orchestration
│   ├── dto/                 # Data transfer objects
│   ├── __init__.py
│   └── ...
├── domain/                   # Domain layer (entities, value objects)
│   ├── entities/            # Pure domain entities
│   ├── repositories/        # Repository interfaces
│   ├── __init__.py
│   └── ...
├── infrastructure/           # Infrastructure layer (DB, messaging)
│   ├── persistence/         # Database implementations
│   ├── messaging/           # Message broker implementations
│   ├── __init__.py
│   └── ...
├── config.py               # Configuration classes
├── logger.py               # Structured logging setup
├── container.py            # Dependency injection container
├── context.py              # Request context management
├── errors.py               # Error handling utilities
├── main.py                 # Application entry point
└── __init__.py
```

## Core Components

### 1. Application Factory (`presentation/app.py`)

The factory pattern creates Flask applications with consistent configuration:

```python
from services.api_service.src.presentation.app import create_app

# Create app with default configuration
app = create_app()

# Create app with custom configuration
from services.api_service.src.config import ProductionConfig
app = create_app(config=ProductionConfig())

# Create app with custom dependency container
from services.api_service.src.container import ServiceContainer
container = ServiceContainer()
app = create_app(container=container)
```

**Factory responsibilities**:
- Load configuration
- Setup logging
- Initialize dependency injection container
- Register middleware and error handlers
- Register blueprints
- Configure CORS
- Setup OpenAPI/Swagger documentation

**Benefits**:
- Easy testing with different configurations
- Reusable app creation logic
- Single point for app initialization

### 2. Configuration (`config.py`)

Environment-specific configuration:

```python
from services.api_service.src.config import get_config

# Auto-detect from FLASK_ENV environment variable
config = get_config()

# Force specific environment
config = get_config("production")

# Access configuration
print(config.MONGODB_URI)
print(config.LOG_LEVEL)
print(config.JWT_SECRET_KEY)
```

**Configuration classes**:
- `Config`: Base configuration with defaults
- `DevelopmentConfig`: DEBUG=True, permissive CORS
- `StagingConfig`: Production-like but testable
- `ProductionConfig`: Strict validation, security checks
- `TestingConfig`: In-memory databases, fast setup

### 3. Structured Logging (`logger.py`)

JSON-formatted logging with correlation ID support:

```python
from services.api_service.src.logger import setup_logging, get_logger

# Setup application logging
setup_logging(log_level="INFO", log_format="json")

# Get logger with context injection
logger = get_logger(__name__)

# Logs automatically include correlation_id from Flask context
logger.info("User login", extra={"user_id": "123"})

# Output (JSON format):
# {
#   "timestamp": "2026-05-18T...",
#   "level": "INFO",
#   "logger": "services.api_service.src.routes.auth",
#   "message": "User login",
#   "correlation_id": "abc-123-def",
#   "request_id": "xyz-789",
#   "user_id": "123"
# }
```

**Features**:
- JSON formatter for log aggregation (ELK, Splunk, DataDog)
- Text formatter for development
- Context-aware adapter that injects correlation IDs
- Exception traceback formatting
- Module/function/line number tracking

### 4. Dependency Injection (`container.py`)

Service container for loose coupling:

```python
from services.api_service.src.container import get_container, init_container

# Get global container (created in factory)
container = get_container()

# Register services
container.register("database", create_database, singleton=True)
container.register("logger", get_logger, singleton=False)

# Register instances
config = get_config()
container.register_instance("config", config)

# Resolve services
db = container.resolve("database")
logger = container.resolve("logger")("my_module")

# Inject in routes
from flask import Blueprint
from services.api_service.src.container import get_container

bp = Blueprint("users", __name__)

@bp.route("/users")
def list_users():
    container = get_container()
    db = container.resolve("database")
    user_service = container.resolve("user_service")
    
    users = user_service.get_all()
    return {"users": users}
```

**Container capabilities**:
- Service registration with factories or instances
- Singleton and transient services
- Lazy initialization
- Easy mocking for testing

### 5. Request Context Management (`context.py`)

Request tracking with correlation IDs:

```python
from services.api_service.src.context import (
    RequestContextManager,
    get_correlation_id,
    get_request_id,
    get_user_id
)

# Setup is done automatically in factory
# RequestContextManager.setup_request_context(app)

# In route handlers, use helpers to get context
@app.route("/jobs")
def get_jobs():
    correlation_id = get_correlation_id()  # Same across microservices
    request_id = get_request_id()           # Unique per request
    user_id = get_user_id()                 # From auth token
    
    logger.info(f"Getting jobs for user {user_id}")
    # Logs automatically include correlation_id
    
    return {"jobs": []}
```

**Features**:
- Generates/tracks correlation IDs across microservices
- Generates unique request IDs per request
- Extracts user ID from JWT token (when auth implemented)
- Adds X-Correlation-ID and X-Request-ID response headers
- Integrates with structured logging

### 6. Error Handling (`errors.py`)

Consistent API error responses:

```python
from services.api_service.src.errors import (
    APIError,
    ValidationError,
    UnauthorizedError,
    NotFoundError,
    ConflictError,
    RateLimitError,
    ServiceUnavailableError
)

@app.route("/users", methods=["POST"])
def create_user():
    # Validation error
    if not request.json.get("email"):
        raise ValidationError("Email is required", details={"field": "email"})
    
    # Conflict (already exists)
    if user_exists(email):
        raise ConflictError(f"User with email {email} already exists")
    
    # Not found
    if not organization_exists(org_id):
        raise NotFoundError("Organization")
    
    # Unauthorized
    if not current_user.can_create_users:
        raise UnauthorizedError("Insufficient permissions")
    
    # Rate limit
    if too_many_requests(current_user.id):
        raise RateLimitError("Too many requests, try again later")
    
    # Service unavailable
    if external_service_down():
        raise ServiceUnavailableError("Payment Service")
    
    return create_new_user(request.json)

# All errors automatically converted to JSON responses:
# {
#   "status": "error",
#   "error": {
#     "code": "VALIDATION_ERROR",
#     "message": "Email is required",
#     "details": {"field": "email"}
#   }
# }
```

**Error types**:
- `ValidationError` (400): Request validation failed
- `UnauthorizedError` (401): Authentication required
- `ForbiddenError` (403): Insufficient permissions
- `NotFoundError` (404): Resource not found
- `ConflictError` (409): Resource already exists
- `RateLimitError` (429): Too many requests
- `ServiceUnavailableError` (503): External service down

### 7. Health Check Endpoints (`presentation/routes/health.py`)

Liveness and readiness probes:

```python
# GET /health
# Lightweight liveness check - is service running?
# Used by load balancers every 10-30 seconds
{
  "status": "healthy",
  "service": "api_service",
  "timestamp": "2026-05-18T..."
}

# GET /health/ready
# Readiness check - is service ready to handle requests?
# Verifies external dependencies (database, cache, message queue)
# Used by orchestrators to route traffic
{
  "status": "ready",
  "service": "api_service",
  "dependencies": {
    "database": "healthy",
    "cache": "healthy",
    "message_queue": "healthy"
  },
  "timestamp": "2026-05-18T..."
}

# GET /health/live
# Kubernetes liveness probe (same as /health)
# Returns 200 if running, 503 if crashed

# GET /health/metrics
# Placeholder for metrics endpoint
# (TODO: Implement with prometheus client)
```

### 8. Blueprints

Modular route organization:

```python
# services/api_service/src/presentation/routes/users.py
from flask import Blueprint, request, jsonify
from services.api_service.src.logger import get_logger

logger = get_logger(__name__)

users_bp = Blueprint(
    "users",
    __name__,
    url_prefix="/api/v1/users"
)

@users_bp.route("", methods=["GET"])
def list_users():
    """
    List all users
    ---
    tags:
      - Users
    responses:
      200:
        description: List of users
    """
    # Implementation here
    return {"users": []}

@users_bp.route("/<user_id>", methods=["GET"])
def get_user(user_id):
    """
    Get user by ID
    ---
    tags:
      - Users
    parameters:
      - name: user_id
        in: path
        required: true
        type: string
    responses:
      200:
        description: User details
      404:
        description: User not found
    """
    # Implementation here
    return {"user": {}}

# Register in app.py
# app.register_blueprint(users_bp)
```

**Blueprint benefits**:
- Organize routes by domain/feature
- Separate concerns
- Easy to test
- URL prefix management
- Swagger documentation per route

### 9. OpenAPI/Swagger Documentation

Automatic API documentation:

```python
# Access at: http://localhost:5000/apidocs/

# Add documentation to routes using docstrings:
@app.route("/users/<user_id>", methods=["GET"])
def get_user(user_id):
    """
    Get user by ID
    ---
    tags:
      - Users
    parameters:
      - name: user_id
        in: path
        required: true
        type: string
        description: User ID
    responses:
      200:
        description: User details
        schema:
          properties:
            id:
              type: string
            email:
              type: string
            name:
              type: string
      404:
        description: User not found
    """
    return get_user_by_id(user_id)
```

## Running the Application

### Development

```bash
# Copy development environment
cp config/environments/.env.development .env

# Install dependencies
pip install -r services/api_service/requirements.txt

# Run Flask application
python -m services.api_service.src.main

# Application starts on http://localhost:5000
# Swagger documentation: http://localhost:5000/apidocs/
# Health check: http://localhost:5000/health
```

### Docker

```bash
# Build image
docker build -f services/api_service/Dockerfile -t ai-microservices/api_service:latest .

# Run container
docker run -p 5000:5000 \
  --env-file config/environments/.env.development \
  ai-microservices/api_service:latest
```

### Docker Compose

```bash
docker-compose up api_service

# View logs
docker-compose logs -f api_service
```

### Kubernetes

```bash
# Create secret with production configuration
kubectl create secret generic api_service-secrets \
  --from-literal=MONGODB_URI='mongodb://...' \
  --from-literal=JWT_SECRET_KEY='...' \
  -n production

# Deploy
kubectl apply -f infrastructure/kubernetes/api_service.yaml

# View logs
kubectl logs -f deployment/api_service -n production

# Port forward for local testing
kubectl port-forward svc/api_service 5000:5000 -n production
```

## Adding New Routes

### Step 1: Create Blueprint

Create `services/api_service/src/presentation/routes/jobs.py`:

```python
from flask import Blueprint, request, jsonify
from services.api_service.src.logger import get_logger
from services.api_service.src.container import get_container
from services.api_service.src.errors import NotFoundError

logger = get_logger(__name__)

jobs_bp = Blueprint(
    "jobs",
    __name__,
    url_prefix="/api/v1/jobs"
)

@jobs_bp.route("", methods=["POST"])
def create_job():
    """Create a new job"""
    container = get_container()
    job_service = container.resolve("job_service")
    
    try:
        job = job_service.create(request.json)
        logger.info(f"Job created: {job.id}", extra={"job_id": job.id})
        return {"job": job.to_dict()}, 201
    except Exception as e:
        logger.error(f"Failed to create job: {e}")
        raise

@jobs_bp.route("/<job_id>", methods=["GET"])
def get_job(job_id):
    """Get job details"""
    container = get_container()
    job_service = container.resolve("job_service")
    
    job = job_service.get_by_id(job_id)
    if not job:
        raise NotFoundError("Job")
    
    return {"job": job.to_dict()}
```

### Step 2: Register Blueprint

Update `services/api_service/src/presentation/app.py`:

```python
from services.api_service.src.presentation.routes.jobs import jobs_bp

def _register_blueprints(app: Flask) -> None:
    """Register all blueprints"""
    app.register_blueprint(health_bp)
    app.register_blueprint(jobs_bp)  # Add this
    logger.debug("Registered blueprints")
```

### Step 3: Implement Service

Create `services/api_service/src/application/use_cases/job_service.py`:

```python
from services.api_service.src.logger import get_logger

logger = get_logger(__name__)

class JobService:
    def __init__(self, repository):
        self.repository = repository
    
    def create(self, data):
        # Validate input
        # Create domain entity
        # Save to repository
        # Publish event
        pass
    
    def get_by_id(self, job_id):
        return self.repository.find_by_id(job_id)
```

### Step 4: Register Service

Update `services/api_service/src/presentation/app.py`:

```python
def create_app(...):
    # ... existing code ...
    
    # Register services in container
    container.register(
        "job_service",
        lambda: JobService(container.resolve("job_repository")),
        singleton=True
    )
```

## Testing

### Unit Tests

```python
# tests/unit/routes/test_health.py
import pytest
from services.api_service.src.presentation.app import create_app
from services.api_service.src.config import TestingConfig

@pytest.fixture
def app():
    app = create_app(config=TestingConfig())
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "healthy"

def test_readiness_check(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    # Verify dependencies
```

### Integration Tests

```python
# tests/integration/test_job_routes.py
def test_create_job(client, db):
    response = client.post(
        "/api/v1/jobs",
        json={
            "job_type": "training",
            "input": {"model": "bert"}
        }
    )
    assert response.status_code == 201
    assert "job_id" in response.json["job"]
```

## Best Practices

### 1. Logging
- Use structured logging with correlation IDs
- Log important business events (create, update, delete)
- Include relevant context in extra fields
- Never log sensitive data (passwords, tokens, PII)

```python
logger.info("User created", extra={"user_id": "123"})  # Good
logger.info(f"Created user: {email}")  # Bad - logs email
```

### 2. Error Handling
- Use appropriate HTTP status codes
- Provide machine-readable error codes
- Include helpful error messages
- Never expose internal implementation details

```python
raise NotFoundError("User")              # Good
return "User not found", 404             # Bad
```

### 3. Configuration
- Use environment variables for all configuration
- Never hardcode secrets
- Validate configuration at startup
- Use type-safe configuration classes

```python
config = get_config()  # Good
db_url = os.getenv("MONGODB_URI")  # Bad - not typed
```

### 4. Dependency Injection
- Register dependencies in container during app creation
- Resolve dependencies in route handlers
- Use lazy loading for expensive resources
- Mock containers in tests

```python
db = container.resolve("database")  # Good
db = MongoDatabase()  # Bad - tight coupling
```

### 5. Blueprints
- Group related routes in blueprints
- Use consistent URL prefixes (/api/v1/...)
- Document Swagger in docstrings
- Keep blueprint logic in service layer

```python
@bp.route("/jobs", methods=["GET"])  # Good - routes
service.get_all_jobs()  # Good - business logic separate
```

## Extensibility

The template supports adding:

- **Authentication**: Implement auth middleware and routes
- **Authorization**: Add permission checks in service layer
- **Validation**: Add Pydantic models for request validation
- **Caching**: Use Redis client from container
- **Database**: Implement repository interfaces
- **Message Queue**: Publish/subscribe events with RabbitMQ
- **Rate Limiting**: Flask-Limiter for rate limiting
- **Monitoring**: Prometheus metrics endpoint
- **Tracing**: Distributed tracing with OpenTelemetry

Each can be added as middleware, services, or blueprints without modifying core factory.

## Troubleshooting

### Application Won't Start

```
ERROR: Configuration validation failed: JWT_SECRET_KEY must be set
```

**Solution**: Set JWT_SECRET_KEY environment variable
```bash
export JWT_SECRET_KEY='<32+ character key>'
```

### Health Check Fails

```
GET /health/ready returns 503
```

**Solution**: Check dependencies in health route
- Verify MongoDB connection string
- Verify Redis is running
- Verify RabbitMQ is running

### Slow Startup

**Solution**: Check logs for initialization issues
```bash
FLASK_ENV=development python -m services.api_service.src.main
```

### Logs Not in JSON

**Solution**: Verify LOG_FORMAT configuration
```bash
export LOG_FORMAT=json
```

## Related Documentation

- [Configuration Guide](../CONFIGURATION.md)
- [Clean Architecture](../CLEAN_ARCHITECTURE.md)
- [Event Contracts](../EVENT_CONTRACTS.md)
- [Testing Strategy](../TESTING.md)
- [Deployment Guide](../DEPLOYMENT.md)
