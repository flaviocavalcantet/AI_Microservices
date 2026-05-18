# Architecture Documentation

## System Overview

This document describes the architectural patterns, design decisions, and component interactions in the AI-Enabled Distributed Backend Platform.

## 1. Architectural Styles

### Clean Architecture

The platform adopts Uncle Bob's Clean Architecture to ensure:

- **Independence from frameworks**: Business logic doesn't depend on Flask, MongoDB, etc.
- **Testability**: Core logic testable without external dependencies
- **Independence of UI**: Business logic works with any presentation layer
- **Independence of the database**: Swap MongoDB for PostgreSQL without touching business logic
- **Independence of any external agency**: Core logic remains pure and isolated

### Event-Driven Architecture

Services communicate asynchronously through domain and integration events:

```
Service A (publishes) → Event Bus (RabbitMQ) → Service B (subscribes)
```

Benefits:
- **Loose coupling**: Services don't need direct knowledge of each other
- **Scalability**: Independent scaling of event producers and consumers
- **Resilience**: Failed services don't block others
- **Auditability**: Complete event history for debugging and compliance

## 2. Service Responsibilities

### api_service

**Purpose**: Main entry point and API gateway

**Key Responsibilities**:
- HTTP endpoint definitions
- Request validation and transformation
- Cross-service orchestration
- Load balancing across service instances

**Domain Events Published**:
- `RequestInitiated`
- `ProcessingCompleted`

**Integration Events Consumed**:
- `UserAuthenticated` (from auth_service)
- `ProcessingResult` (from ai_worker)

**Dependencies**:
- auth_service (for validation)
- ai_worker (for processing)
- notification_service (for feedback)

### auth_service

**Purpose**: Identity and access management

**Key Responsibilities**:
- User registration and credential management
- Authentication (token generation)
- Authorization (permission verification)
- Session management

**Domain Events Published**:
- `UserRegistered`
- `UserAuthenticated`
- `PermissionGranted`

**No External Service Dependencies**: auth_service is independent

### ai_worker

**Purpose**: Long-running AI/ML tasks

**Key Responsibilities**:
- Model inference and training
- Batch processing
- Result computation
- Task status tracking

**Domain Events Published**:
- `ProcessingStarted`
- `ProcessingCompleted`
- `ProcessingFailed`

**Integration Events Consumed**:
- `ProcessingRequested` (from api_service)

**Dependencies**:
- Uses Celery for task queuing
- MongoDB for result storage

### notification_service

**Purpose**: Asynchronous user notifications

**Key Responsibilities**:
- Email delivery
- Push notifications
- Notification templating
- Delivery status tracking

**Integration Events Consumed**:
- `ProcessingCompleted` (from ai_worker)
- `UserRegistered` (from auth_service)

**No Service Dependencies**: notification_service is read-only (consumes events)

## 3. Data Flow Patterns

### Synchronous Request Flow

```
Client HTTP Request
    ↓
api_service (Presentation Layer)
    ↓
api_service (Application Layer - Use Case)
    ↓
api_service (Domain Layer - Business Logic)
    ↓
Infrastructure Layer (DB, External Services)
    ↓
HTTP Response
```

### Asynchronous Event Flow

```
Service A (Domain Layer)
    ↓ (publishes event)
Event Bus (RabbitMQ)
    ↓ (routes to subscribers)
Service B (Infrastructure Layer - Event Handler)
    ↓
Service B (Application Layer - Use Case triggered by event)
    ↓
Service B (Domain Layer - Business Logic)
    ↓
Infrastructure Layer (DB, External Services)
    ↓
Optional: Publishes new event
```

## 4. Dependency Injection

All services use constructor-based dependency injection:

```python
class CreateUserUseCase:
    def __init__(self, user_repository: IUserRepository, 
                 event_publisher: IEventPublisher):
        self.user_repository = user_repository
        self.event_publisher = event_publisher
```

**Benefits**:
- Loose coupling
- Easy testing with mocks
- Clear dependencies
- Testability without containers

## 5. Error Handling Strategy

### Domain Layer Exceptions

```python
class DomainException(Exception):
    """Base exception for all domain errors"""
    pass

class InvalidUserException(DomainException):
    """User violates business rules"""
    pass

class DuplicateEmailException(DomainException):
    """Email already registered"""
    pass
```

### Application Layer Exception Translation

```python
try:
    user = create_user_use_case.execute(request)
except DuplicateEmailException:
    raise ApplicationException("Email already registered", status=409)
```

### Presentation Layer HTTP Translation

```python
@app.errorhandler(ApplicationException)
def handle_application_error(error):
    return {"error": error.message}, error.status_code
```

## 6. Testing Strategy

### Unit Tests (Domain Layer)
- Test business logic in isolation
- No external dependencies
- Fast, deterministic

```python
def test_user_creation_with_valid_data():
    user = User.create(email="test@example.com", name="Test")
    assert user.email == "test@example.com"
```

### Integration Tests (Application Layer)
- Test use cases with mock infrastructure
- Verify business logic flow
- Mock external services

```python
def test_create_user_use_case():
    repo_mock = Mock(IUserRepository)
    event_pub_mock = Mock(IEventPublisher)
    use_case = CreateUserUseCase(repo_mock, event_pub_mock)
    
    use_case.execute(CreateUserRequest(...))
    
    repo_mock.save.assert_called_once()
    event_pub_mock.publish.assert_called_once()
```

### End-to-End Tests (Service Level)
- Full service integration tests
- Real or containerized dependencies
- Verify cross-service behavior

## 7. Configuration Management

### Environment Variables

Service configuration via `.env` files:

```
# Database
MONGODB_URI=mongodb://localhost:27017/ai_platform

# Message Queue
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Service
SERVICE_PORT=5000
SERVICE_LOG_LEVEL=INFO
```

### Configuration Classes

```python
class Config:
    """Base configuration"""
    MONGODB_URI = os.getenv("MONGODB_URI")
    RABBITMQ_URL = os.getenv("RABBITMQ_URL")

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
```

## 8. Scalability Patterns

### Horizontal Scaling

Each service can run multiple instances:

```yaml
services:
  api_service:
    replicas: 3  # Scale independently
  ai_worker:
    replicas: 5  # More workers for compute tasks
```

Load balancing via RabbitMQ (task queue) for workers, nginx for HTTP services.

### Asynchronous Processing

Long-running tasks via Celery:

```python
@celery.task
def process_data(data_id):
    # Runs in worker process
    # Can be scaled independently
    return perform_computation(data_id)
```

### Caching Strategy

- **Application cache**: In-memory (Redis)
- **Distributed cache**: Redis cluster
- **Database cache**: MongoDB indexes

## 9. Security Considerations

### Authentication

JWT tokens with RS256 (asymmetric):

```python
token = jwt.encode(
    payload={"user_id": user_id, "exp": expiry},
    key=PRIVATE_KEY,
    algorithm="RS256"
)
```

### Authorization

Role-based access control (RBAC):

```python
@require_role("admin")
def delete_user():
    ...
```

### Data Protection

- Encryption at rest (MongoDB field-level encryption)
- Encryption in transit (HTTPS, TLS for RabbitMQ)
- Sensitive data never logged

## 10. Monitoring and Observability

### Structured Logging

JSON-formatted logs:

```json
{
  "timestamp": "2026-05-15T10:30:00Z",
  "level": "INFO",
  "service": "api_service",
  "user_id": "123",
  "action": "create_user",
  "duration_ms": 245,
  "status": "success"
}
```

### Distributed Tracing

OpenTelemetry integration for request tracing across services.

### Metrics

Prometheus metrics:
- Request latency
- Error rates
- Queue depths
- Database connection pools

## 11. Deployment Topology

### Development

```
Docker Compose (single machine)
├── MongoDB
├── RabbitMQ
├── api_service
├── auth_service
├── ai_worker
└── notification_service
```

### Production

```
Kubernetes Cluster
├── Namespace: backend
├── Services:
│   ├── api_service (deployment × 3)
│   ├── auth_service (deployment × 2)
│   ├── ai_worker (deployment × 5)
│   └── notification_service (deployment × 2)
├── StatefulSets:
│   ├── MongoDB (replication set)
│   └── RabbitMQ (cluster)
└── ConfigMaps & Secrets
```

## 12. Design Decisions

### Why Clean Architecture?

**Decision**: Isolate business logic from frameworks and infrastructure

**Rationale**:
- Business logic is most valuable and least likely to change
- Framework choices are implementation details
- Pure domain logic is easier to test and reason about

**Trade-off**: Slightly more boilerplate code for significant gains in maintainability

### Why Event-Driven?

**Decision**: Asynchronous communication between services

**Rationale**:
- Services remain loosely coupled
- Easier to add new consumers without modifying producers
- Natural fit for async tasks (AI inference, notifications)

**Trade-off**: Eventual consistency instead of strong consistency

### Why MongoDB?

**Decision**: Document database for flexible schema

**Rationale**:
- AI workload data often has irregular schema
- Good for rapid iteration
- Horizontal scaling capabilities

**Trade-off**: Not ideal for complex relational queries

## 13. Future Evolution Paths

- **GraphQL Gateway**: Alternative to REST API
- **gRPC Services**: For high-throughput internal communication
- **CQRS Pattern**: Separate read and write models for ai_worker
- **Saga Pattern**: Distributed transactions across services
- **Machine Learning Pipeline**: Data science framework integration
