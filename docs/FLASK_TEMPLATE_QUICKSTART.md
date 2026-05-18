# Flask Application Template - Quick Start

This is a quick reference for using the production-grade Flask application template.

## 5-Minute Start

### 1. Copy Environment Configuration

```bash
cp config/environments/.env.development .env
```

### 2. Install Dependencies

```bash
pip install -r services/api_service/requirements.txt
```

### 3. Run Application

```bash
python -m services.api_service.src.main
```

### 4. Test the API

```bash
# Health check
curl http://localhost:5000/health

# Readiness check
curl http://localhost:5000/health/ready

# API documentation
open http://localhost:5000/apidocs/
```

## File Overview

### Core Application Files

| File | Purpose | Key Classes |
|------|---------|------------|
| `main.py` | Entry point | `main()`, `validate_startup()` |
| `presentation/app.py` | Flask factory | `create_app()`, `_register_blueprints()`, `_setup_swagger()` |
| `config.py` | Configuration | `Config`, `DevelopmentConfig`, `StagingConfig`, `ProductionConfig`, `TestingConfig` |
| `logger.py` | Structured logging | `JSONFormatter`, `TextFormatter`, `setup_logging()`, `get_logger()` |
| `container.py` | Dependency injection | `ServiceContainer`, `get_container()`, `init_container()` |
| `context.py` | Request context | `RequestContextManager`, `get_correlation_id()`, `get_request_id()`, `get_user_id()` |
| `errors.py` | Error handling | `APIError`, `ValidationError`, `NotFoundError`, etc., `register_error_handlers()` |

### Route Blueprint Files

| File | Purpose | URL Prefix |
|------|---------|-----------|
| `presentation/routes/health.py` | Health checks | `/health` |
| `presentation/routes/` | (Add more blueprints here) | `/api/v1/...` |

### Infrastructure Files

| Directory | Purpose |
|-----------|---------|
| `domain/entities/` | Pure domain entities (framework-independent) |
| `domain/repositories/` | Repository interfaces (no implementation) |
| `application/use_cases/` | Business logic orchestration |
| `application/dto/` | Data transfer objects |
| `infrastructure/persistence/` | Database implementations (MongoDB) |
| `infrastructure/messaging/` | Message queue implementations (RabbitMQ) |

## Common Tasks

### Add a New Route

1. Create blueprint file: `services/api_service/src/presentation/routes/users.py`

```python
from flask import Blueprint, jsonify
from services.api_service.src.logger import get_logger

logger = get_logger(__name__)

users_bp = Blueprint("users", __name__, url_prefix="/api/v1/users")

@users_bp.route("", methods=["GET"])
def list_users():
    """List all users"""
    return {"users": []}

@users_bp.route("/<user_id>", methods=["GET"])
def get_user(user_id):
    """Get user by ID"""
    return {"user": {"id": user_id}}
```

2. Register in `presentation/app.py`:

```python
from services.api_service.src.presentation.routes.users import users_bp

def _register_blueprints(app: Flask) -> None:
    app.register_blueprint(health_bp)
    app.register_blueprint(users_bp)  # Add this
```

### Add a New Service

1. Create in `application/use_cases/user_service.py`:

```python
from services.api_service.src.logger import get_logger

logger = get_logger(__name__)

class UserService:
    def __init__(self, repository):
        self.repository = repository
    
    def get_all(self):
        return self.repository.find_all()
    
    def get_by_id(self, user_id):
        return self.repository.find_by_id(user_id)
```

2. Register in container (`presentation/app.py`):

```python
def create_app(...):
    # ... existing code ...
    
    container.register(
        "user_service",
        lambda: UserService(container.resolve("user_repository")),
        singleton=True
    )
```

3. Use in routes:

```python
@users_bp.route("/<user_id>", methods=["GET"])
def get_user(user_id):
    container = get_container()
    user_service = container.resolve("user_service")
    return {"user": user_service.get_by_id(user_id)}
```

### Handle Custom Error

```python
from services.api_service.src.errors import ValidationError, NotFoundError

@users_bp.route("", methods=["POST"])
def create_user():
    # Validation error
    if not request.json.get("email"):
        raise ValidationError("Email is required", details={"field": "email"})
    
    # Not found error
    if not department_exists(request.json.get("department_id")):
        raise NotFoundError("Department")
    
    # Success
    return {"user": new_user}, 201
```

### Access Request Context

```python
from services.api_service.src.context import (
    get_correlation_id,
    get_request_id,
    get_user_id
)
from services.api_service.src.logger import get_logger

logger = get_logger(__name__)

@users_bp.route("/<user_id>", methods=["GET"])
def get_user(user_id):
    correlation_id = get_correlation_id()
    request_id = get_request_id()
    current_user_id = get_user_id()
    
    # Logs automatically include correlation_id
    logger.info(f"Getting user {user_id}")
    
    return {"user": {...}}
```

### Add Environment Variable

1. Update `config.py`:

```python
@dataclass
class Config:
    # ... existing config ...
    MY_NEW_VAR: str = os.getenv("MY_NEW_VAR", "default_value")
```

2. Set in `.env.development`:

```bash
MY_NEW_VAR=my_custom_value
```

3. Access in app:

```python
config = get_config()
value = config.MY_NEW_VAR
```

## Running in Different Environments

### Development (Local Machine)

```bash
export FLASK_ENV=development
export LOG_FORMAT=text
export LOG_LEVEL=DEBUG

python -m services.api_service.src.main
```

### Staging

```bash
export FLASK_ENV=staging
export LOG_FORMAT=json
export LOG_LEVEL=INFO

# Set other environment variables...
python -m services.api_service.src.main
```

### Production (Kubernetes)

```bash
# Secrets are injected via Kubernetes Secret
export FLASK_ENV=production
export LOG_FORMAT=json
export LOG_LEVEL=WARNING

python -m services.api_service.src.main
```

## Testing

### Run Health Check

```bash
# Liveness probe
curl http://localhost:5000/health

# Readiness probe
curl http://localhost:5000/health/ready

# With correlation ID
curl -H "X-Correlation-ID: my-trace-id" http://localhost:5000/health
```

### Run Unit Tests

```bash
pytest tests/unit/ -v
```

### Run Integration Tests

```bash
pytest tests/integration/ -v
```

### Run All Tests

```bash
pytest -v
```

## Architecture Highlights

### Layered Architecture

```
HTTP Request
    ↓
[Middleware] - Request context, correlation ID
    ↓
[Routes] - Parse HTTP, call services
    ↓
[Application] - Business logic orchestration
    ↓
[Domain] - Pure business rules
    ↓
[Infrastructure] - Database, messaging
    ↓
Response
```

### Dependency Flow

```
Presentation (Routes)
    ↓ depends on ↓
Application (Services)
    ↓ depends on ↓
Domain (Entities, Repositories)
    ↓ implements ↓
Infrastructure (MongoDB, RabbitMQ)
```

### Configuration Flow

```
.env file (highest priority)
    ↓ or ↓
.env.{ENVIRONMENT}
    ↓ or ↓
Environment variables
    ↓ or ↓
Code defaults (lowest priority)
```

## Key Patterns

### 1. Factory Pattern

```python
app = create_app()  # Default configuration
app = create_app(config=ProductionConfig())  # Custom configuration
```

### 2. Dependency Injection

```python
container = get_container()
db = container.resolve("database")
```

### 3. Blueprints

```python
users_bp = Blueprint("users", __name__, url_prefix="/api/v1/users")
app.register_blueprint(users_bp)
```

### 4. Error Handling

```python
raise NotFoundError("User")
# Automatically converted to JSON response with 404 status
```

### 5. Structured Logging

```python
logger = get_logger(__name__)
logger.info("User created", extra={"user_id": "123"})
# Automatically includes correlation_id
```

## Troubleshooting

### Port Already in Use

```bash
# Use different port
export SERVICE_PORT=5001
python -m services.api_service.src.main
```

### ModuleNotFoundError

```bash
# Install dependencies
pip install -r services/api_service/requirements.txt
```

### Configuration Error

```bash
# Check environment variables
env | grep FLASK_ENV
env | grep MONGODB_URI

# Validate configuration
python -c "from services.api_service.src.config import get_config; print(get_config())"
```

### Health Check Fails

```bash
# Check individual dependencies
curl http://localhost:5000/health/ready

# View logs
tail -f logs/api_service.log
```

## Next Steps

1. **Implement Domain Layer**: Create entities and repository interfaces
2. **Implement Application Layer**: Create use cases and DTOs
3. **Implement Infrastructure**: Implement repositories for MongoDB
4. **Add Authentication**: Implement JWT-based auth middleware
5. **Add Authorization**: Implement permission checks in services
6. **Add Validation**: Use Pydantic models for request validation
7. **Add Caching**: Use Redis for caching
8. **Add Rate Limiting**: Use Flask-Limiter
9. **Add Monitoring**: Add Prometheus metrics
10. **Add Tracing**: Add OpenTelemetry for distributed tracing

## Related Documentation

- [Complete Flask Application Template Guide](FLASK_APPLICATION_TEMPLATE.md)
- [Configuration Management](CONFIGURATION.md)
- [Clean Architecture](CLEAN_ARCHITECTURE.md)
- [Testing Strategy](TESTING.md)
- [Deployment Guide](DEPLOYMENT.md)

## Support

For issues or questions:

1. Check logs: `docker-compose logs -f api_service`
2. Check configuration: `echo $FLASK_ENV && echo $MONGODB_URI`
3. Read documentation: See related docs above
4. Check health: `curl http://localhost:5000/health/ready`
