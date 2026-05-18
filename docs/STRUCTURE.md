# Project Structure Guide

This document explains the folder and file structure of the monorepo, naming conventions, and where to place new code.

## Directory Tree

```
AI_MICROSERVICES/
│
├── services/                          # All microservices
│   ├── api_service/                   # API gateway & orchestration
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── main.py               # Service entry point
│   │   │   ├── domain/               # Pure business logic (framework-agnostic)
│   │   │   │   ├── __init__.py
│   │   │   │   ├── entities/         # Domain objects (User, Request, etc.)
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── *.py
│   │   │   │   ├── repositories/     # Repository interfaces (abstract contracts)
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── base_repository.py
│   │   │   │   │   └── *_repository.py
│   │   │   │   ├── services/         # Domain services (business logic)
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── *.py
│   │   │   │   └── exceptions.py     # Domain-specific exceptions
│   │   │   │
│   │   │   ├── application/          # Use cases & application logic
│   │   │   │   ├── __init__.py
│   │   │   │   ├── dto/              # Data Transfer Objects (request/response contracts)
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── request_*.py
│   │   │   │   │   └── response_*.py
│   │   │   │   ├── use_cases/        # Application orchestration
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── *.py
│   │   │   │   └── exceptions.py     # Application exceptions
│   │   │   │
│   │   │   ├── infrastructure/       # External concerns & technical implementations
│   │   │   │   ├── __init__.py
│   │   │   │   ├── persistence/      # Database implementations
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── mongo/        # MongoDB-specific implementations
│   │   │   │   │   │   ├── __init__.py
│   │   │   │   │   │   └── *_repository.py
│   │   │   │   │   └── models.py     # ORM/document models
│   │   │   │   ├── messaging/        # Event publishing & RabbitMQ
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── event_publisher.py
│   │   │   │   │   └── event_handlers.py
│   │   │   │   ├── config/           # Infrastructure configuration
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── database.py
│   │   │   │   │   └── messaging.py
│   │   │   │   └── external/         # External service clients
│   │   │   │       ├── __init__.py
│   │   │   │       └── *.py
│   │   │   │
│   │   │   ├── presentation/         # HTTP layer & user interface
│   │   │   │   ├── __init__.py
│   │   │   │   ├── app.py            # Flask app factory
│   │   │   │   ├── routes/           # HTTP endpoints
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── *.py
│   │   │   │   ├── middleware/       # Flask middleware
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── error_handler.py
│   │   │   │   │   ├── auth.py
│   │   │   │   │   └── logging.py
│   │   │   │   └── serializers.py    # JSON serialization
│   │   │   │
│   │   │   └── config.py             # Service configuration & env loading
│   │   │
│   │   ├── tests/                    # Mirrored structure with tests
│   │   │   ├── __init__.py
│   │   │   ├── unit/                 # Unit tests (domain layer)
│   │   │   ├── integration/          # Integration tests (application layer)
│   │   │   ├── e2e/                  # End-to-end tests
│   │   │   ├── fixtures/             # Test fixtures & mocks
│   │   │   └── conftest.py           # Pytest configuration
│   │   │
│   │   ├── Dockerfile                # Service container image
│   │   ├── requirements.txt           # Service dependencies
│   │   └── README.md                 # Service documentation
│   │
│   ├── auth_service/                 # Same structure as api_service
│   ├── ai_worker/                    # Same structure as api_service
│   └── notification_service/         # Same structure as api_service
│
├── shared/                            # Shared libraries & common code
│   ├── shared_kernel/                # Core domain abstractions
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── entities.py           # Base entity classes
│   │   │   ├── value_objects.py      # Base value object classes
│   │   │   ├── repositories.py       # Base repository interfaces
│   │   │   ├── services.py           # Base service classes
│   │   │   ├── exceptions.py         # Common domain exceptions
│   │   │   └── types.py              # Common type definitions
│   │   ├── tests/
│   │   ├── requirements.txt
│   │   └── README.md
│   │
│   ├── shared_events/                # Event definitions & contracts
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── base_event.py         # Base event classes
│   │   │   ├── domain_events.py      # Domain event definitions
│   │   │   ├── integration_events.py # Integration event definitions
│   │   │   ├── registry.py           # Event registry & discovery
│   │   │   ├── serializers.py        # Event serialization
│   │   │   └── schemas/              # Event schema definitions
│   │   │       ├── __init__.py
│   │   │       └── *.py
│   │   ├── tests/
│   │   ├── requirements.txt
│   │   └── README.md
│   │
│   └── shared_utils/                 # Utilities & helpers
│       ├── src/
│       │   ├── __init__.py
│       │   ├── logging.py            # Structured logging
│       │   ├── exceptions.py         # Common exception classes
│       │   ├── validators.py         # Validation utilities
│       │   ├── helpers.py            # General helper functions
│       │   ├── date_time.py          # Date/time utilities
│       │   ├── string.py             # String manipulation utilities
│       │   ├── collections.py        # Collection utilities
│       │   └── decorators.py         # Common decorators
│       ├── tests/
│       ├── requirements.txt
│       └── README.md
│
├── infrastructure/                    # Infrastructure & deployment
│   ├── docker/                        # Docker configuration
│   │   ├── Dockerfile.api_service
│   │   ├── Dockerfile.auth_service
│   │   ├── Dockerfile.ai_worker
│   │   ├── Dockerfile.notification_service
│   │   └── .dockerignore
│   │
│   └── kubernetes/                    # Kubernetes manifests
│       ├── namespaces.yaml
│       ├── api_service.yaml
│       ├── auth_service.yaml
│       ├── ai_worker.yaml
│       ├── notification_service.yaml
│       └── monitoring/
│
├── config/                            # Configuration & environment
│   └── environments/
│       ├── .env.development           # Development environment
│       ├── .env.staging               # Staging environment
│       ├── .env.production            # Production environment
│       └── .env.example               # Template for new environments
│
├── scripts/                           # Development & deployment scripts
│   ├── dev/                           # Development scripts
│   │   ├── setup.sh                   # Initial setup
│   │   ├── start.sh                   # Start all services
│   │   ├── stop.sh                    # Stop all services
│   │   ├── migrate.sh                 # Database migrations
│   │   └── seed.sh                    # Seed test data
│   │
│   ├── testing/                       # Testing scripts
│   │   ├── run_tests.sh               # Run all tests
│   │   ├── run_unit_tests.sh          # Run unit tests only
│   │   ├── run_integration_tests.sh   # Run integration tests
│   │   └── coverage.sh                # Generate coverage report
│   │
│   └── deployment/                    # Deployment scripts
│       ├── build_images.sh            # Build Docker images
│       ├── push_images.sh             # Push to registry
│       ├── deploy.sh                  # Deploy to Kubernetes
│       └── rollback.sh                # Rollback deployment
│
├── docs/                              # Documentation
│   ├── ARCHITECTURE.md                # Architectural decisions & patterns
│   ├── STRUCTURE.md                   # This file
│   ├── API_SPECIFICATION.md           # API documentation
│   ├── DATABASE_SCHEMA.md             # Data model documentation
│   ├── DEPLOYMENT.md                  # Deployment procedures
│   ├── TESTING.md                     # Testing strategy
│   └── TROUBLESHOOTING.md             # Common issues & solutions
│
├── docker-compose.yml                 # Local development orchestration
├── pyproject.toml                     # Root project metadata
├── setup.py                           # Package setup
├── .gitignore                         # Git ignore rules
├── .dockerignore                      # Docker build ignore rules
├── .env.example                       # Environment template
└── README.md                          # Project overview
```

## File Naming Conventions

### Python Modules

| Type | Naming | Example |
|------|--------|---------|
| Entities | `{entity_name}.py` | `user.py`, `request.py` |
| Repositories (interfaces) | `{entity_name}_repository.py` | `user_repository.py` |
| Repositories (implementations) | `mongo_{entity_name}_repository.py` | `mongo_user_repository.py` |
| Use Cases | `{action}_{entity_name}_use_case.py` | `create_user_use_case.py`, `delete_user_use_case.py` |
| DTOs | `{action}_{entity_name}_request.py`, `{entity_name}_response.py` | `create_user_request.py`, `user_response.py` |
| Routes | `{entity_name}_routes.py` | `user_routes.py` |
| Middleware | `{concern}_middleware.py` | `auth_middleware.py` |
| Event Handlers | `{event_name}_handler.py` | `user_created_handler.py` |
| Services | `{service_name}_service.py` | `email_service.py` |
| Tests | `test_{module_name}.py` | `test_user_repository.py` |

### Class Naming

| Type | Naming | Example |
|------|--------|---------|
| Entities | PascalCase | `User`, `Request`, `ProcessingJob` |
| DTOs | PascalCase + Suffix | `CreateUserRequest`, `UserResponse` |
| Repositories | PascalCase + "Repository" | `UserRepository`, `IUserRepository` |
| Use Cases | PascalCase + "UseCase" | `CreateUserUseCase` |
| Services | PascalCase + "Service" | `EmailService` |
| Exceptions | PascalCase + "Exception" or "Error" | `UserAlreadyExistsException` |
| Events | PascalCase + "Event" | `UserCreatedEvent` |
| Interfaces | PrefixedWithI | `IUserRepository`, `IEventPublisher` |

### Constant Naming

```python
# Module-level constants (UPPER_CASE_WITH_UNDERSCORES)
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30
USER_ROLES = ["admin", "user", "guest"]

# Enum constants
class UserStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
```

## Import Organization

**Order of imports in Python files:**

```python
# 1. Standard library
import os
import sys
from typing import Optional, List
from datetime import datetime

# 2. Third-party libraries
from flask import Blueprint, request
import pymongo
from celery import Celery

# 3. Local imports (shared modules)
from shared_kernel.entities import BaseEntity
from shared_events.base_event import DomainEvent
from shared_utils.logging import get_logger

# 4. Local imports (same service)
from domain.entities import User
from infrastructure.persistence.mongo.user_repository import MongoUserRepository
```

## Service Internal Layer Structure

### Domain Layer Best Practices

```
domain/
├── entities/
│   ├── __init__.py
│   ├── base.py                    # Base entity class (use shared_kernel)
│   ├── user.py                    # User entity with business logic
│   ├── email.py                   # Value object for email
│   └── user_status.py             # Enum or value object
├── repositories/
│   ├── __init__.py
│   └── user_repository.py         # IUserRepository interface
├── services/
│   ├── __init__.py
│   └── user_validator_service.py  # Pure business logic service
└── exceptions.py                  # Domain-specific exceptions
```

**Rules:**
- ✅ DO: Pure Python, no framework imports
- ✅ DO: Type hints on all functions
- ✅ DO: Clear, testable business logic
- ❌ DON'T: Import from Flask, MongoDB, etc.
- ❌ DON'T: Direct database access
- ❌ DON'T: External API calls

### Application Layer Best Practices

```
application/
├── dto/
│   ├── __init__.py
│   ├── create_user_request.py     # Input contract
│   └── user_response.py           # Output contract
├── use_cases/
│   ├── __init__.py
│   ├── create_user_use_case.py    # Orchestrates domain logic
│   ├── delete_user_use_case.py
│   └── get_user_use_case.py
└── exceptions.py                  # Application exceptions
```

**Rules:**
- ✅ DO: Orchestrate domain logic
- ✅ DO: Handle transactions
- ✅ DO: Validate inputs
- ✅ DO: Publish domain events
- ❌ DON'T: Implement business logic
- ❌ DON'T: Mix with HTTP concerns

### Infrastructure Layer Best Practices

```
infrastructure/
├── persistence/
│   ├── mongo/
│   │   ├── __init__.py
│   │   ├── user_repository.py     # Implements IUserRepository
│   │   └── models.py              # MongoDB document models
│   └── models.py                  # ORM/document definitions
├── messaging/
│   ├── __init__.py
│   ├── event_publisher.py         # RabbitMQ implementation
│   └── event_handlers.py          # Event subscription handlers
├── config/
│   ├── __init__.py
│   ├── database.py                # MongoDB connection
│   └── messaging.py               # RabbitMQ setup
└── external/
    ├── __init__.py
    └── *.py                       # External service clients
```

**Rules:**
- ✅ DO: Implement domain interfaces
- ✅ DO: Handle technical details
- ✅ DO: Manage external connections
- ❌ DON'T: Expose infrastructure details upward
- ❌ DON'T: Contain business logic

### Presentation Layer Best Practices

```
presentation/
├── app.py                         # Flask app factory
├── routes/
│   ├── __init__.py
│   ├── user_routes.py             # User endpoints
│   └── health_routes.py           # Health check endpoints
├── middleware/
│   ├── __init__.py
│   ├── error_handler.py           # Exception → HTTP response
│   ├── auth.py                    # Authentication middleware
│   └── logging.py                 # Request/response logging
└── serializers.py                 # JSON serialization
```

**Rules:**
- ✅ DO: Define HTTP endpoints
- ✅ DO: Handle HTTP concerns
- ✅ DO: Delegate to use cases
- ✅ DO: Transform exceptions to HTTP responses
- ❌ DON'T: Implement business logic
- ❌ DON'T: Access database directly

## Cross-Service Communication

### Event Publishing Pattern

```
Service A (Domain Layer)
    ↓
Service A (Application Layer) catches domain event
    ↓
Service A (Infrastructure) publishes to RabbitMQ
    ↓
Service B (Infrastructure) event handler triggered
    ↓
Service B (Application) use case executed
```

## Test Structure

```
tests/
├── __init__.py
├── conftest.py                    # Pytest fixtures
├── fixtures/
│   ├── __init__.py
│   └── *.py                       # Test data & mocks
├── unit/
│   ├── __init__.py
│   └── domain/
│       ├── __init__.py
│       ├── test_user.py           # Test User entity
│       └── test_user_repository.py
├── integration/
│   ├── __init__.py
│   └── application/
│       ├── __init__.py
│       └── test_create_user_use_case.py
└── e2e/
    ├── __init__.py
    └── test_user_api.py           # Full HTTP endpoint tests
```

## Adding New Features

### Step 1: Add Domain Logic
```
domain/entities/new_feature.py
domain/repositories/new_feature_repository.py
```

### Step 2: Add Application Logic
```
application/dto/new_feature_request.py
application/dto/new_feature_response.py
application/use_cases/create_new_feature_use_case.py
```

### Step 3: Add Infrastructure
```
infrastructure/persistence/mongo/new_feature_repository.py
```

### Step 4: Add Presentation
```
presentation/routes/new_feature_routes.py
```

### Step 5: Add Tests
```
tests/unit/domain/test_new_feature.py
tests/integration/application/test_create_new_feature_use_case.py
tests/e2e/test_new_feature_api.py
```

## Shared Code Guidelines

### When to Use shared_kernel

- Base entity and value object classes
- Common repository interfaces
- Standard exception classes
- Common domain patterns

### When to Use shared_events

- Domain event definitions
- Integration event schemas
- Event serialization logic
- Event registry

### When to Use shared_utils

- Logging utilities
- String, date, collection helpers
- Validation functions
- Common decorators
- Type definitions

### When to Create Service-Specific Code

- Domain entities specific to service
- Business logic specific to service
- Service-specific DTOs
- Service-specific repositories
