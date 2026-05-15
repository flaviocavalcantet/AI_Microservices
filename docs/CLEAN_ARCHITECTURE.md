# Clean Architecture for Flask Services

## Overview

Clean Architecture organizes application code into concentric layers with clear dependencies. Code dependencies flow inward, with the Domain Layer completely isolated from external frameworks.

```
┌─────────────────────────────────────────┐
│         PRESENTATION LAYER              │ HTTP Handlers, Routes, Controllers
│         (presentation/)                 │ ← Can depend on: Application, Domain
│                                         │ ← Cannot depend on: Frameworks directly
├─────────────────────────────────────────┤
│         APPLICATION LAYER               │ Use Cases, DTOs, Orchestration
│         (application/)                  │ ← Can depend on: Domain
│                                         │ ← Cannot depend on: Frameworks, Database
├─────────────────────────────────────────┤
│         DOMAIN LAYER                    │ Pure Business Logic, Entities, Rules
│         (domain/)                       │ ← Can depend on: Nothing external
│                                         │ ← Completely framework-independent
├─────────────────────────────────────────┤
│         INFRASTRUCTURE LAYER            │ Database, External Services, Adapters
│         (infrastructure/)               │ ← Can depend on: Domain (contracts)
│                                         │ ← Cannot violate Domain contracts
└─────────────────────────────────────────┘

         ↑ Dependency Direction (Points Inward)
```

## Layer Responsibilities

### 1. DOMAIN LAYER (`domain/`)

**Primary Responsibility**: Pure business logic independent of any framework

#### Responsibilities
- Define business entities and value objects
- Implement core business rules and validations
- Define repository interfaces (contracts)
- Handle domain exceptions
- Maintain the Ubiquitous Language

#### Components

```python
# domain/entities/user.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class User:
    """Domain entity - pure business logic, no persistence concerns"""
    id: str
    email: str
    name: str
    password_hash: str
    is_active: bool
    created_at: datetime
    
    @staticmethod
    def create(email: str, name: str, password_hash: str) -> "User":
        """Factory method - business logic for user creation"""
        if not email or "@" not in email:
            raise ValueError("Invalid email format")
        if not name or len(name) < 2:
            raise ValueError("Name must be at least 2 characters")
        if len(password_hash) < 60:  # bcrypt hash minimum
            raise ValueError("Password hash invalid")
        
        return User(
            id="",  # Will be assigned by repository
            email=email.lower(),
            name=name.strip(),
            password_hash=password_hash,
            is_active=True,
            created_at=datetime.utcnow()
        )
    
    def is_valid_password(self, plain_password: str, hasher) -> bool:
        """Domain business rule: password validation"""
        return hasher.verify(plain_password, self.password_hash)

# domain/repositories/user_repository.py
from abc import ABC, abstractmethod
from typing import Optional

class IUserRepository(ABC):
    """Repository interface - contract for data persistence
    
    NOTE: This is a DOMAIN interface. Implementation is in INFRASTRUCTURE.
    """
    
    @abstractmethod
    def save(self, user: User) -> str:
        """Save user and return ID
        
        Raises: DuplicateEmailException if email already exists
        """
        pass
    
    @abstractmethod
    def find_by_id(self, user_id: str) -> Optional[User]:
        """Find user by ID"""
        pass
    
    @abstractmethod
    def find_by_email(self, email: str) -> Optional[User]:
        """Find user by email"""
        pass

# domain/exceptions.py
class DomainException(Exception):
    """Base exception for all domain errors"""
    pass

class InvalidUserException(DomainException):
    """User violates business rules"""
    pass

class DuplicateEmailException(DomainException):
    """Email already registered - business constraint violation"""
    pass
```

#### Allowed Dependencies
- ✅ Other domain modules
- ✅ Python standard library
- ✅ Pure type definitions (dataclasses, enums)

#### Forbidden Dependencies
- ❌ Flask, Django, FastAPI
- ❌ Database drivers (pymongo, SQLAlchemy)
- ❌ External APIs
- ❌ Message queues
- ❌ Any framework-specific decorators

#### Testing Domain Layer
```python
# tests/unit/domain/test_user.py
import pytest
from services.api_service.domain.entities.user import User
from services.api_service.domain.exceptions import InvalidUserException

class TestUserEntity:
    """Domain entities tested in isolation - NO external dependencies"""
    
    def test_user_creation_with_valid_data(self):
        """Should create user with valid data"""
        user = User.create(
            email="john@example.com",
            name="John Doe",
            password_hash="$2b$12$" + "x" * 53  # Valid bcrypt hash
        )
        assert user.email == "john@example.com"
        assert user.name == "John Doe"
        assert user.is_active is True
    
    def test_user_creation_with_invalid_email(self):
        """Should raise exception for invalid email"""
        with pytest.raises(ValueError):
            User.create(
                email="invalid-email",
                name="John Doe",
                password_hash="$2b$12$" + "x" * 53
            )
```

---

### 2. APPLICATION LAYER (`application/`)

**Primary Responsibility**: Orchestrate domain logic and coordinate between Domain and Infrastructure

#### Responsibilities
- Implement use cases (application services)
- Define Data Transfer Objects (DTOs)
- Coordinate with repositories
- Handle transactions and error mapping
- Publish domain events
- Orchestrate complex workflows

#### Components

```python
# application/dto/create_user_request.py
from dataclasses import dataclass

@dataclass
class CreateUserRequest:
    """DTO: Input contract for creating a user
    
    NOTE: DTOs exist to decouple the API contract from domain entities
    """
    email: str
    name: str
    password: str

# application/dto/user_response.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class UserResponse:
    """DTO: Output contract for user representation
    
    NOTE: Never expose internal domain entity structure directly to API
    """
    id: str
    email: str
    name: str
    is_active: bool
    created_at: datetime
    
    @staticmethod
    def from_domain(user):
        """Convert domain entity to API response"""
        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            is_active=user.is_active,
            created_at=user.created_at
        )

# application/use_cases/create_user_use_case.py
from typing import Tuple
from services.api_service.domain.entities.user import User
from services.api_service.domain.repositories.user_repository import IUserRepository
from services.api_service.domain.exceptions import DuplicateEmailException
from services.shared_events.base_event import IEventPublisher

class CreateUserUseCase:
    """Use Case: Create a new user
    
    Orchestrates:
    - Repository for persistence
    - Event publisher for notifications
    - Domain entity creation
    - Error handling and translation
    """
    
    def __init__(
        self,
        user_repository: IUserRepository,
        event_publisher: IEventPublisher,
        password_hasher  # Infrastructure dependency injected
    ):
        self.user_repository = user_repository
        self.event_publisher = event_publisher
        self.password_hasher = password_hasher
    
    def execute(self, request: CreateUserRequest) -> Tuple[str, dict]:
        """Execute use case: create user
        
        Returns: (user_id, response_data)
        Raises: ApplicationException (translates domain exceptions)
        """
        
        # Check if user already exists (business rule)
        existing = self.user_repository.find_by_email(request.email)
        if existing:
            raise DuplicateEmailException(
                f"User with email {request.email} already exists"
            )
        
        # Create domain entity (business logic encapsulated in domain)
        password_hash = self.password_hasher.hash(request.password)
        user = User.create(
            email=request.email,
            name=request.name,
            password_hash=password_hash
        )
        
        # Persist user (infrastructure responsibility)
        user_id = self.user_repository.save(user)
        user.id = user_id
        
        # Publish domain event (for other services to react to)
        self.event_publisher.publish({
            "event_type": "UserCreated",
            "user_id": user_id,
            "email": request.email,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return user_id, {"id": user_id, "email": request.email}

# application/exceptions.py
class ApplicationException(Exception):
    """Base exception for application-level errors
    
    Translates domain exceptions to HTTP responses
    """
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class UserAlreadyExistsError(ApplicationException):
    def __init__(self, email: str):
        super().__init__(
            f"User with email {email} already exists",
            status_code=409
        )
```

#### Allowed Dependencies
- ✅ Domain layer (entities, repositories, exceptions)
- ✅ Other application modules (DTOs, use cases)
- ✅ Infrastructure interfaces/abstractions (only contracts)
- ✅ Python standard library

#### Forbidden Dependencies
- ❌ Flask, HTTP handlers, routes
- ❌ Database implementations (only interfaces)
- ❌ Direct infrastructure details
- ❌ Presentation logic

#### Testing Application Layer
```python
# tests/integration/application/test_create_user_use_case.py
import pytest
from unittest.mock import Mock
from services.api_service.application.use_cases.create_user_use_case import CreateUserUseCase
from services.api_service.application.dto.create_user_request import CreateUserRequest

class TestCreateUserUseCase:
    """Application layer tested with mocked infrastructure"""
    
    @pytest.fixture
    def use_case_with_mocks(self):
        """Setup use case with mocked dependencies"""
        user_repo = Mock()
        event_pub = Mock()
        password_hasher = Mock()
        password_hasher.hash.return_value = "$2b$12$" + "x" * 53
        
        return (
            CreateUserUseCase(user_repo, event_pub, password_hasher),
            user_repo,
            event_pub,
            password_hasher
        )
    
    def test_create_user_success(self, use_case_with_mocks):
        """Should create user and publish event"""
        use_case, repo, event_pub, hasher = use_case_with_mocks
        repo.find_by_email.return_value = None
        repo.save.return_value = "user_123"
        
        request = CreateUserRequest(
            email="john@example.com",
            name="John Doe",
            password="securepass123"
        )
        
        user_id, response = use_case.execute(request)
        
        # Verify repository was called
        repo.find_by_email.assert_called_once_with("john@example.com")
        repo.save.assert_called_once()
        
        # Verify event was published
        event_pub.publish.assert_called_once()
        assert user_id == "user_123"
    
    def test_create_user_duplicate_email(self, use_case_with_mocks):
        """Should raise exception for duplicate email"""
        use_case, repo, _, _ = use_case_with_mocks
        repo.find_by_email.return_value = Mock()  # User exists
        
        with pytest.raises(DuplicateEmailException):
            use_case.execute(CreateUserRequest(
                email="existing@example.com",
                name="John Doe",
                password="pass123"
            ))
```

---

### 3. INFRASTRUCTURE LAYER (`infrastructure/`)

**Primary Responsibility**: Implement technical concerns and adapt external systems to domain contracts

#### Responsibilities
- Implement repository interfaces (database access)
- Connect to external services (APIs, queues)
- Handle configuration and environment setup
- Provide infrastructure-specific implementations
- Event publishing/subscription
- Logging and monitoring

#### Components

```python
# infrastructure/persistence/mongo/user_repository.py
from typing import Optional
from pymongo import MongoClient
from services.api_service.domain.entities.user import User
from services.api_service.domain.repositories.user_repository import IUserRepository
from services.api_service.domain.exceptions import DuplicateEmailException

class MongoUserRepository(IUserRepository):
    """MongoDB implementation of user repository
    
    NOTE: Infrastructure detail. Domain only sees IUserRepository interface.
    Can be swapped with PostgreSQL, Redis, etc. without domain changes.
    """
    
    def __init__(self, db: MongoClient):
        self.collection = db["ai_platform"]["users"]
        # Create indexes for performance
        self.collection.create_index("email", unique=True)
    
    def save(self, user: User) -> str:
        """Save user to MongoDB"""
        doc = {
            "email": user.email,
            "name": user.name,
            "password_hash": user.password_hash,
            "is_active": user.is_active,
            "created_at": user.created_at
        }
        
        try:
            result = self.collection.insert_one(doc)
            return str(result.inserted_id)
        except Exception as e:
            if "duplicate key" in str(e):
                raise DuplicateEmailException(f"Email {user.email} already exists")
            raise
    
    def find_by_id(self, user_id: str) -> Optional[User]:
        """Find user by ID"""
        from bson import ObjectId
        doc = self.collection.find_one({"_id": ObjectId(user_id)})
        if not doc:
            return None
        return self._doc_to_entity(doc)
    
    def find_by_email(self, email: str) -> Optional[User]:
        """Find user by email"""
        doc = self.collection.find_one({"email": email.lower()})
        if not doc:
            return None
        return self._doc_to_entity(doc)
    
    def _doc_to_entity(self, doc: dict) -> User:
        """Convert MongoDB document to domain entity"""
        return User(
            id=str(doc["_id"]),
            email=doc["email"],
            name=doc["name"],
            password_hash=doc["password_hash"],
            is_active=doc["is_active"],
            created_at=doc["created_at"]
        )

# infrastructure/messaging/event_publisher.py
import json
from typing import Dict, Any
import pika

class RabbitMQEventPublisher:
    """Publish domain events to RabbitMQ
    
    NOTE: Infrastructure detail. Domain publishes to interface, not directly to queue.
    """
    
    def __init__(self, rabbitmq_url: str):
        self.connection = pika.BlockingConnection(
            pika.URLParameters(rabbitmq_url)
        )
        self.channel = self.connection.channel()
        self.channel.exchange_declare(
            exchange="domain_events",
            exchange_type="topic",
            durable=True
        )
    
    def publish(self, event: Dict[str, Any]):
        """Publish event to message broker"""
        routing_key = f"domain.{event['event_type'].lower()}"
        
        self.channel.basic_publish(
            exchange="domain_events",
            routing_key=routing_key,
            body=json.dumps(event),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Persistent
                content_type="application/json"
            )
        )

# infrastructure/config/database.py
from pymongo import MongoClient
import os

class DatabaseConfig:
    """Database configuration and connection management"""
    
    @staticmethod
    def get_connection():
        """Get MongoDB connection from environment"""
        mongodb_uri = os.getenv(
            "MONGODB_URI",
            "mongodb://admin:admin123@localhost:27017/ai_platform?authSource=admin"
        )
        return MongoClient(mongodb_uri)
```

#### Allowed Dependencies
- ✅ Domain interfaces (repositories, exceptions)
- ✅ External libraries (pymongo, requests, pika)
- ✅ Database drivers and APIs
- ✅ Configuration management

#### Forbidden Dependencies
- ❌ Flask routes or controllers
- ❌ Presentation layer logic
- ❌ Application DTOs (only via adapters)
- ❌ Domain implementation details

#### Testing Infrastructure Layer
```python
# tests/integration/infrastructure/test_mongo_user_repository.py
import pytest
from unittest.mock import Mock, patch
from services.api_service.infrastructure.persistence.mongo.user_repository import (
    MongoUserRepository
)

class TestMongoUserRepository:
    """Infrastructure layer with mock database"""
    
    @pytest.fixture
    def repository(self):
        """Setup repository with mocked MongoDB"""
        mock_db = Mock()
        return MongoUserRepository(mock_db)
    
    def test_save_user_success(self, repository):
        """Should save user to MongoDB"""
        user = Mock()
        user.email = "john@example.com"
        user.name = "John Doe"
        
        # Mock MongoDB response
        repository.collection.insert_one.return_value.inserted_id = "123"
        
        result = repository.save(user)
        
        assert result == "123"
        repository.collection.insert_one.assert_called_once()
```

---

### 4. PRESENTATION LAYER (`presentation/`)

**Primary Responsibility**: Handle HTTP concerns and translate between HTTP and Application

#### Responsibilities
- Define HTTP routes and endpoints
- Parse HTTP requests
- Validate inputs (from HTTP perspective)
- Call application use cases
- Format HTTP responses
- Handle middleware concerns (authentication, logging)

#### Components

```python
# presentation/routes/user_routes.py
from flask import Blueprint, request, jsonify
from services.api_service.application.use_cases.create_user_use_case import CreateUserUseCase
from services.api_service.application.dto.create_user_request import CreateUserRequest
from services.api_service.application.exceptions import ApplicationException
from services.api_service.presentation.middleware.auth import require_auth

user_routes = Blueprint("users", __name__, url_prefix="/api/v1/users")

# These are injected by the app factory
_create_user_use_case = None

def set_use_cases(create_user):
    """Dependency injection for use cases"""
    global _create_user_use_case
    _create_user_use_case = create_user

@user_routes.route("", methods=["POST"])
def create_user():
    """Create a new user
    
    HTTP Endpoint Responsibility:
    - Parse HTTP request
    - Validate HTTP input
    - Call application layer
    - Format HTTP response
    - Handle HTTP errors
    """
    try:
        # 1. Parse request body
        data = request.get_json()
        if not data:
            return {"error": "Request body required"}, 400
        
        # 2. Validate input (HTTP level)
        if not data.get("email"):
            return {"error": "Email required"}, 400
        if not data.get("password"):
            return {"error": "Password required"}, 400
        
        # 3. Create DTO (bridge to application)
        dto = CreateUserRequest(
            email=data["email"],
            name=data.get("name", ""),
            password=data["password"]
        )
        
        # 4. Call use case (application layer)
        user_id, response_data = _create_user_use_case.execute(dto)
        
        # 5. Return HTTP response
        return {
            "status": "success",
            "data": response_data
        }, 201
    
    except ApplicationException as e:
        # 6. Translate application exceptions to HTTP
        return {
            "status": "error",
            "error": e.message
        }, e.status_code
    
    except Exception as e:
        # 7. Handle unexpected errors
        return {
            "status": "error",
            "error": "Internal server error"
        }, 500

@user_routes.route("<user_id>", methods=["GET"])
@require_auth
def get_user(user_id):
    """Get user by ID (requires authentication)"""
    # Implementation...
    pass

# presentation/middleware/auth.py
from functools import wraps
from flask import request, jsonify
import jwt
import os

def require_auth(f):
    """Middleware: Require JWT authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        
        if not token:
            return {"error": "Unauthorized"}, 401
        
        try:
            payload = jwt.decode(
                token,
                os.getenv("JWT_SECRET_KEY"),
                algorithms=["HS256"]
            )
            request.user_id = payload["user_id"]
        except jwt.InvalidTokenError:
            return {"error": "Invalid token"}, 401
        
        return f(*args, **kwargs)
    
    return decorated_function

# presentation/app.py
from flask import Flask, jsonify
from services.api_service.infrastructure.config.database import DatabaseConfig
from services.api_service.infrastructure.persistence.mongo.user_repository import MongoUserRepository
from services.api_service.application.use_cases.create_user_use_case import CreateUserUseCase
from services.api_service.presentation.routes.user_routes import user_routes, set_use_cases

def create_app():
    """Application factory with dependency injection"""
    app = Flask(__name__)
    
    # 1. Initialize infrastructure
    db = DatabaseConfig.get_connection()
    user_repository = MongoUserRepository(db)
    
    # 2. Instantiate use cases
    create_user_use_case = CreateUserUseCase(user_repository)
    
    # 3. Inject use cases into routes
    set_use_cases(create_user_use_case)
    
    # 4. Register blueprints
    app.register_blueprint(user_routes)
    
    # 5. Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return {"error": "Not found"}, 404
    
    @app.errorhandler(500)
    def internal_error(e):
        return {"error": "Internal server error"}, 500
    
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
```

#### Allowed Dependencies
- ✅ Application layer (use cases, DTOs)
- ✅ Application exceptions
- ✅ Flask and HTTP libraries
- ✅ Middleware for cross-cutting concerns

#### Forbidden Dependencies
- ❌ Domain layer directly (only through application)
- ❌ Infrastructure implementations
- ❌ Database access
- ❌ Message queue operations

#### Testing Presentation Layer
```python
# tests/e2e/test_user_api.py
import pytest
from unittest.mock import Mock, patch

class TestUserAPI:
    """Presentation layer (API) tested with mocked application layer"""
    
    @pytest.fixture
    def client(self):
        """Setup Flask test client"""
        app = create_app()
        app.config["TESTING"] = True
        return app.test_client()
    
    def test_create_user_endpoint(self, client):
        """Should create user via HTTP endpoint"""
        response = client.post("/api/v1/users", json={
            "email": "john@example.com",
            "name": "John Doe",
            "password": "securepass123"
        })
        
        assert response.status_code == 201
        assert response.json["status"] == "success"
        assert response.json["data"]["id"]
    
    def test_create_user_validation(self, client):
        """Should validate required fields"""
        response = client.post("/api/v1/users", json={
            "name": "John Doe"
            # Missing email and password
        })
        
        assert response.status_code == 400
        assert "Email required" in response.json["error"]
```

---

## Dependency Flow Example

```
HTTP Request (POST /users)
    ↓
Presentation Layer (user_routes.py)
    - Parse JSON
    - Validate HTTP input
    ↓
Application Layer (create_user_use_case.py)
    - Create DTO
    - Check business rules (no duplicate emails)
    ↓
Domain Layer (User entity)
    - Validate user data (domain rules)
    - Create entity
    ↓
Infrastructure Layer (MongoUserRepository)
    - Persist to MongoDB
    - Implement IUserRepository interface
    ↓
Application Layer
    - Publish event
    ↓
Presentation Layer
    - Format HTTP response (201 Created)
    ↓
HTTP Response with user data
```

## Key Principles

### 1. Dependency Inversion
- Domain defines interfaces (repositories)
- Infrastructure implements interfaces
- Application depends on interfaces, not implementations

```python
# GOOD: Application depends on interface (domain)
class CreateUserUseCase:
    def __init__(self, user_repository: IUserRepository):
        self.user_repository = user_repository  # Interface

# BAD: Application directly depends on implementation
class CreateUserUseCase:
    def __init__(self):
        self.user_repository = MongoUserRepository()  # Implementation
```

### 2. Single Responsibility
- Domain: Business logic only
- Application: Use case orchestration
- Infrastructure: Technical implementation
- Presentation: HTTP handling

### 3. Testability
- Domain: Testable in isolation (no mocks needed)
- Application: Testable with mocked infrastructure
- Infrastructure: Testable with mocked external services
- Presentation: Testable with mocked application layer

### 4. Framework Independence
- Domain has ZERO framework imports
- Can swap Flask for FastAPI without changing domain
- Can swap MongoDB for PostgreSQL without changing domain

## Implementation Checklist

- [ ] Domain layer contains only business logic
- [ ] Domain has no external dependencies
- [ ] Repository interfaces defined in domain
- [ ] Use cases in application layer orchestrate domain
- [ ] Infrastructure implements domain interfaces
- [ ] Presentation layer thin (delegates to application)
- [ ] All dependencies point inward
- [ ] Each layer has corresponding tests
- [ ] Unit tests for domain (no mocks)
- [ ] Integration tests for application (mocked infrastructure)
- [ ] E2E tests for presentation (mocked application)

## References

- [Clean Architecture by Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
- [Dependency Inversion Principle](https://en.wikipedia.org/wiki/Dependency_inversion_principle)
