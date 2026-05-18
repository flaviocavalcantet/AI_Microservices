# Project Structure Summary

## Complete Folder Tree

```
AI_MICROSERVICES/
│
├── services/
│   ├── api_service/
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── domain/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── entities/
│   │   │   │   ├── repositories/
│   │   │   │   ├── services/
│   │   │   │   └── exceptions.py
│   │   │   ├── application/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── dto/
│   │   │   │   ├── use_cases/
│   │   │   │   └── exceptions.py
│   │   │   ├── infrastructure/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── persistence/
│   │   │   │   ├── messaging/
│   │   │   │   ├── config/
│   │   │   │   └── external/
│   │   │   └── presentation/
│   │   │       ├── __init__.py
│   │   │       ├── app.py
│   │   │       ├── routes/
│   │   │       ├── middleware/
│   │   │       └── serializers.py
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   ├── integration/
│   │   │   ├── e2e/
│   │   │   ├── fixtures/
│   │   │   └── conftest.py
│   │   ├── requirements.txt
│   │   └── Dockerfile (via infrastructure/docker/)
│   │
│   ├── auth_service/
│   │   ├── src/
│   │   ├── tests/
│   │   └── requirements.txt
│   │
│   ├── ai_worker/
│   │   ├── src/
│   │   ├── tests/
│   │   └── requirements.txt
│   │
│   └── notification_service/
│       ├── src/
│       ├── tests/
│       └── requirements.txt
│
├── shared/
│   ├── shared_kernel/
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── entities.py
│   │   │   ├── value_objects.py
│   │   │   ├── repositories.py
│   │   │   ├── services.py
│   │   │   ├── exceptions.py
│   │   │   └── types.py
│   │   ├── tests/
│   │   ├── requirements.txt
│   │   └── README.md
│   │
│   ├── shared_events/
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── base_event.py
│   │   │   ├── domain_events.py
│   │   │   ├── integration_events.py
│   │   │   ├── registry.py
│   │   │   ├── serializers.py
│   │   │   └── schemas/
│   │   ├── tests/
│   │   ├── requirements.txt
│   │   └── README.md
│   │
│   └── shared_utils/
│       ├── src/
│       │   ├── __init__.py
│       │   ├── logging.py
│       │   ├── exceptions.py
│       │   ├── validators.py
│       │   ├── helpers.py
│       │   ├── date_time.py
│       │   ├── string.py
│       │   ├── collections.py
│       │   └── decorators.py
│       ├── tests/
│       ├── requirements.txt
│       └── README.md
│
├── infrastructure/
│   ├── docker/
│   │   ├── Dockerfile.api_service
│   │   ├── Dockerfile.auth_service
│   │   ├── Dockerfile.ai_worker
│   │   ├── Dockerfile.notification_service
│   │   └── .dockerignore
│   │
│   └── kubernetes/
│       ├── namespaces.yaml
│       ├── api_service.yaml
│       ├── auth_service.yaml
│       ├── ai_worker.yaml
│       ├── notification_service.yaml
│       ├── mongodb.yaml
│       ├── rabbitmq.yaml
│       └── network-policies.yaml
│
├── config/
│   └── environments/
│       ├── .env.development
│       ├── .env.staging
│       ├── .env.production
│       └── .env.example
│
├── scripts/
│   ├── dev/
│   │   ├── setup.sh
│   │   ├── start.sh
│   │   └── stop.sh
│   │
│   ├── testing/
│   │   ├── run_tests.sh
│   │   ├── run_unit_tests.sh
│   │   └── run_integration_tests.sh
│   │
│   └── deployment/
│       ├── build_images.sh
│       ├── push_images.sh
│       └── deploy.sh
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── STRUCTURE.md
│   ├── TESTING.md
│   ├── API_SPECIFICATION.md
│   ├── DATABASE_SCHEMA.md
│   ├── DEPLOYMENT.md
│   └── TROUBLESHOOTING.md
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── conftest.py
│
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── setup.py
├── .gitignore
├── .env.example
├── README.md
├── QUICKSTART.md
└── CONTRIBUTING.md
```

## Services Overview

### 1. API Service (Port 5000)
**Responsibility**: Main API gateway and request orchestration

**Key Components**:
- HTTP REST endpoints for request management
- Cross-service orchestration logic
- Request routing and load balancing
- Response formatting and error handling

**Dependencies**: auth_service, ai_worker, notification_service

---

### 2. Auth Service (Port 5001)
**Responsibility**: Authentication and authorization

**Key Components**:
- User registration and login
- JWT token generation and validation
- Permission and role management
- User profile management

**Dependencies**: None (independent service)

---

### 3. AI Worker (Port 5002)
**Responsibility**: Asynchronous AI/ML task processing

**Key Components**:
- Model inference and training
- Batch processing
- Result computation and storage
- Task status tracking
- Celery integration for async processing

**Dependencies**: Task queue (RabbitMQ), Result store (Redis/MongoDB)

---

### 4. Notification Service (Port 5003)
**Responsibility**: Asynchronous notification delivery

**Key Components**:
- Email notification sending
- Push notification support
- SMS notification capability
- Notification templating
- Delivery status tracking

**Dependencies**: Email service, Celery workers

---

## Shared Modules Overview

### shared_kernel
Core domain abstractions used across all services:
- `BaseEntity`: Foundation for domain entities
- `ValueObject`: Immutable domain objects
- `IRepository`: Repository interface contracts
- `DomainException`: Base exception class
- Common domain patterns and utilities

### shared_events
Event definitions and contracts for inter-service communication:
- `DomainEvent`: Events from domain layer
- `IntegrationEvent`: Events for cross-service communication
- `EventRegistry`: Event discovery mechanism
- Event serialization/deserialization
- Event schema definitions

### shared_utils
Cross-cutting utilities and helpers:
- Structured logging utilities
- Custom exception classes
- Input validation functions
- String, date, collection helpers
- Common decorators and type hints

---

## Technology Stack

### Core Framework
- **Python 3.12+**: Modern Python with type hints
- **Flask**: Lightweight web framework
- **PyJWT**: JWT token handling

### Data & Storage
- **MongoDB**: Document database
- **Redis**: Caching and session store
- **SQLAlchemy** (optional): ORM for relational data

### Messaging & Task Processing
- **RabbitMQ**: Message broker
- **Celery**: Distributed task processing
- **Flower**: Celery monitoring UI

### Security
- **bcrypt**: Password hashing
- **python-jose**: Cryptographic operations
- **passlib**: Password hashing framework

### Development & Testing
- **pytest**: Testing framework
- **pytest-cov**: Coverage reporting
- **black**: Code formatter
- **flake8**: Style checker
- **mypy**: Type checker

### Containerization & Orchestration
- **Docker**: Container images
- **Docker Compose**: Local orchestration
- **Kubernetes**: Production orchestration
- **Helm** (optional): Kubernetes package manager

---

## Clean Architecture Implementation

Each service follows Clean Architecture with strict dependency rules:

```
┌─────────────────────────────────┐
│     Presentation Layer          │ ← HTTP Controllers, Routes, Middleware
│  (presentation/)                │
├─────────────────────────────────┤
│     Application Layer           │ ← Use Cases, DTOs, Orchestration
│  (application/)                 │
├─────────────────────────────────┤
│     Domain Layer                │ ← Business Logic, Entities, Repositories
│  (domain/)                      │   (Framework-Independent!)
├─────────────────────────────────┤
│     Infrastructure Layer        │ ← Database, Messaging, External Services
│  (infrastructure/)              │
└─────────────────────────────────┘

Dependency Rule: Only point inward (toward Domain Layer)
Domain Layer: Zero external dependencies
```

---

## Key Architectural Decisions

### 1. Event-Driven Communication
**Why**: Services remain loosely coupled and independently scalable
- Services communicate through RabbitMQ event bus
- Domain events from domain layer
- Integration events for cross-service communication

### 2. MongoDB as Primary Store
**Why**: Flexible schema for AI workload data
- Document-oriented for irregular data structures
- Horizontal scalability
- Rich query language

### 3. Celery for Async Tasks
**Why**: Handle long-running AI/ML operations
- Distributed task processing
- Retry logic and error handling
- Task monitoring and tracking

### 4. Microservices Over Monolith
**Why**: Independent scaling and deployment
- Each service handles specific domain
- Services can scale independently
- Technology choices per service
- Faster development and iteration

### 5. Clean Architecture
**Why**: Business logic remains framework-independent
- Testable without external dependencies
- Easy to swap implementations
- Clear separation of concerns
- Long-term maintainability

---

## Directory Responsibility

| Directory | Purpose |
|-----------|---------|
| `services/` | Microservices implementations |
| `shared/` | Reusable libraries across services |
| `infrastructure/` | Docker images and Kubernetes manifests |
| `config/` | Environment-specific configurations |
| `scripts/` | Developer tooling and automation |
| `docs/` | Architecture and operational documentation |
| `tests/` | Root-level integration tests |

---

## Getting Started Path

1. **Understand Architecture**: Read `docs/ARCHITECTURE.md`
2. **Know the Structure**: Review `docs/STRUCTURE.md`
3. **Setup Development**: Run `./scripts/dev/setup.sh`
4. **Start Services**: Run `./scripts/dev/start.sh`
5. **Write Code**: Follow the architecture layers
6. **Test Thoroughly**: Write tests in `tests/` directories
7. **Deploy**: Follow `docs/DEPLOYMENT.md`

---

## Next Steps

✅ **Folder structure created**  
✅ **Documentation generated**  
✅ **Docker configuration prepared**  
✅ **Development scripts ready**  
✅ **Kubernetes manifests started**  

**To begin development**:
```bash
cd c:\Codes\AI_MICROSERVICES
./scripts/dev/setup.sh
./scripts/dev/start.sh
pytest
```

**For more information**: See `QUICKSTART.md`, `README.md`, or `docs/` folder
