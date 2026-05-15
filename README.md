# AI-Enabled Distributed Backend Platform

A production-grade, microservices-based backend platform designed for AI/ML workloads, built with Python 3.12+, Flask, MongoDB, RabbitMQ, and Celery.

## Project Overview

This monorepo contains a distributed system following **Clean Architecture** and **Event-Driven Architecture** principles. The platform is designed to be:

- **Scalable**: Microservices architecture with asynchronous processing
- **Maintainable**: Framework-independent business logic, strong separation of concerns
- **Testable**: Deep dependency injection, domain-driven design
- **Cross-platform**: Runs on Windows and Linux with containerization support
- **Production-ready**: Comprehensive logging, error handling, security patterns

## Architecture Principles

### Clean Architecture Layers

Each service implements four distinct layers:

1. **Domain Layer** (`/domain`)
   - Pure business logic, framework-agnostic
   - Entities, Value Objects, Business Rules
   - Domain Repositories (interfaces only)
   - No external dependencies

2. **Application Layer** (`/application`)
   - Use cases and business logic orchestration
   - DTOs for input/output contracts
   - Application Services
   - Depends on Domain Layer

3. **Infrastructure Layer** (`/infrastructure`)
   - Technical implementations of domain contracts
   - Database access, external service clients
   - Messaging adapters, caching, file storage
   - Framework-specific integrations

4. **Presentation Layer** (`/presentation`)
   - HTTP endpoints, request/response handling
   - Controllers/Routes, Middleware
   - Request validation, serialization
   - Thin layer that delegates to Application Layer

### Event-Driven Communication

Services communicate through a RabbitMQ-based event bus:
- **Domain Events**: Published by the Domain Layer
- **Integration Events**: Published by Application Layer
- **Event Handlers**: Asynchronous processing via Celery

### Dependency Rule

> Code dependencies should only point inward (toward the center).
> The Domain Layer is fully isolated and testable without external dependencies.

```
Presentation → Application → Domain ← Infrastructure
```

## Services

### api-service
**Responsibility**: API gateway and orchestration service

- RESTful API endpoints
- Cross-cutting concerns (rate limiting, request/response transformation)
- Orchestrates calls to other services
- Routes events to appropriate handlers

**Tech Stack**: Flask, Flask-RESTful, PyJWT

### auth-service
**Responsibility**: Authentication and Authorization

- User registration and login
- JWT token generation and validation
- Permission and role management
- User profile management

**Tech Stack**: Flask, PyJWT, bcrypt, python-jose

### ai-worker
**Responsibility**: AI/ML Workload Processing

- Long-running inference and training tasks
- Batch processing of AI models
- Result computation and storage
- Health monitoring and error recovery

**Tech Stack**: Flask, Celery, scikit-learn, TensorFlow/PyTorch (optional)

### notification-service
**Responsibility**: Asynchronous Notifications

- Email notifications
- Push notifications
- SMS notifications
- Notification templating and scheduling

**Tech Stack**: Flask, Celery, python-dotenv, EmailService

## Shared Modules

### shared-kernel
**Responsibility**: Core domain abstractions

- Base Entity and Value Object classes
- Common domain exceptions
- Repository interfaces
- Service locator patterns

### shared-events
**Responsibility**: Event definitions and contracts

- Domain event base classes
- Integration event schemas
- Event registry
- Event serialization/deserialization

### shared-utils
**Responsibility**: Cross-cutting utilities

- Logging and tracing
- Error handling and custom exceptions
- Type hints and validators
- Helper utilities (date, string, collection helpers)

## Project Structure

```
AI_MICROSERVICES/
├── services/
│   ├── api-service/
│   ├── auth-service/
│   ├── ai-worker/
│   └── notification-service/
├── shared/
│   ├── shared-kernel/
│   ├── shared-events/
│   └── shared-utils/
├── infrastructure/
│   ├── docker/
│   │   ├── Dockerfile.api-service
│   │   ├── Dockerfile.auth-service
│   │   ├── Dockerfile.ai-worker
│   │   └── Dockerfile.notification-service
│   └── kubernetes/
├── config/
│   └── environments/
│       ├── .env.development
│       ├── .env.staging
│       └── .env.production
├── scripts/
│   ├── dev/
│   ├── testing/
│   └── deployment/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── API_SPECIFICATION.md
│   ├── DATABASE_SCHEMA.md
│   └── DEPLOYMENT.md
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- MongoDB
- RabbitMQ

### Development Setup

```bash
# Clone and navigate to project
cd AI_MICROSERVICES

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Start services with docker-compose
docker-compose up -d

# Run migrations
./scripts/dev/migrate.sh

# Start services locally
python -m services.api_service.main
```

### Running Tests

```bash
# All tests
pytest

# Specific service
pytest services/api-service/tests

# With coverage
pytest --cov=services --cov-report=html
```

## Development Workflow

1. **Feature Development**: Implement in the appropriate service layer
2. **Testing**: Write tests in `/tests` following the layer structure
3. **Events**: Define domain/integration events in `shared-events`
4. **Shared Code**: Extract to `shared-kernel` or `shared-utils` as needed
5. **Documentation**: Update relevant docs in `/docs`

## Environment Configuration

Services read from `.env` files:

```bash
# Development
cp config/environments/.env.development .env

# Production
cp config/environments/.env.production .env
```

## Deployment

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for:
- Docker image building
- Kubernetes manifests
- CI/CD pipeline configuration
- Health checks and monitoring

## Monitoring & Logging

- **Logging**: Structured logging to stdout (for container collection)
- **Tracing**: OpenTelemetry integration ready
- **Metrics**: Prometheus-ready endpoints
- **Health Checks**: Liveness and readiness probes

## Contributing

### Coding Standards

- Follow PEP 8 with Black formatter
- Type hints for all public APIs
- Comprehensive docstrings for public methods
- 80-120 character line length

### Commit Convention

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
Scopes: `api-service`, `auth-service`, `ai-worker`, `notification-service`, `shared-kernel`

## License

Proprietary - Internal Use Only
