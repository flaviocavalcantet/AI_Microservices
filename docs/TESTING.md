# Testing Guide

## Overview

The testing strategy follows Clean Architecture principles with three levels of tests:

1. **Unit Tests** (Domain Layer)
2. **Integration Tests** (Application Layer)
3. **End-to-End Tests** (Full Service)

## Unit Tests (Domain Layer)

### Purpose
Test pure business logic without framework or infrastructure dependencies.

### Location
```
services/{service}/tests/unit/domain/
shared/{module}/tests/unit/
```

### Example: Testing a Domain Entity

```python
# services/api-service/tests/unit/domain/test_user.py
import pytest
from services.api_service.domain.entities.user import User

class TestUser:
    def test_user_creation_with_valid_data(self):
        """User entity should be created with valid email and name"""
        user = User.create(
            email="user@example.com",
            name="John Doe"
        )
        
        assert user.email == "user@example.com"
        assert user.name == "John Doe"
        assert user.is_active is True
    
    def test_user_creation_with_invalid_email(self):
        """User entity should raise exception for invalid email"""
        with pytest.raises(ValueError):
            User.create(
                email="invalid-email",
                name="John Doe"
            )
```

### Characteristics
- ✅ No external dependencies
- ✅ No Flask, MongoDB, RabbitMQ imports
- ✅ Fast execution (< 1ms per test)
- ✅ Deterministic
- ✅ Full business logic coverage

## Integration Tests (Application Layer)

### Purpose
Test use cases with mocked infrastructure dependencies.

### Location
```
services/{service}/tests/integration/application/
shared/{module}/tests/integration/
```

### Example: Testing a Use Case

```python
# services/api-service/tests/integration/application/test_create_user_use_case.py
import pytest
from unittest.mock import Mock
from services.api_service.application.use_cases.create_user_use_case import CreateUserUseCase
from services.api_service.application.dto.create_user_request import CreateUserRequest

class TestCreateUserUseCase:
    @pytest.fixture
    def use_case_with_mocks(self):
        """Fixture providing use case with mocked dependencies"""
        user_repo_mock = Mock()
        event_pub_mock = Mock()
        use_case = CreateUserUseCase(user_repo_mock, event_pub_mock)
        return use_case, user_repo_mock, event_pub_mock
    
    def test_create_user_publishes_event(self, use_case_with_mocks):
        """Creating a user should publish UserCreatedEvent"""
        use_case, repo_mock, event_pub_mock = use_case_with_mocks
        
        request = CreateUserRequest(
            email="user@example.com",
            name="John Doe"
        )
        
        response = use_case.execute(request)
        
        # Verify repository was called
        repo_mock.save.assert_called_once()
        
        # Verify event was published
        event_pub_mock.publish.assert_called_once()
        assert "UserCreatedEvent" in str(event_pub_mock.publish.call_args)
```

### Characteristics
- ✅ Mock infrastructure layer
- ✅ Test application orchestration
- ✅ Verify use case behavior
- ✅ No database or queue calls
- ✅ Medium execution speed (10-100ms per test)

## End-to-End Tests (Service Level)

### Purpose
Test full service with containerized dependencies.

### Location
```
services/{service}/tests/e2e/
```

### Example: Testing an API Endpoint

```python
# services/api-service/tests/e2e/test_user_api.py
import pytest
from flask import Flask

class TestUserAPI:
    @pytest.fixture
    def client(self):
        """Fixture providing Flask test client"""
        app = create_app()
        app.config['TESTING'] = True
        return app.test_client()
    
    def test_create_user_endpoint(self, client):
        """POST /users should create a new user"""
        response = client.post('/users', json={
            'email': 'user@example.com',
            'name': 'John Doe'
        })
        
        assert response.status_code == 201
        assert response.json['id']
        assert response.json['email'] == 'user@example.com'
```

### Characteristics
- ✅ Full service integration
- ✅ Real HTTP requests
- ✅ Docker-compose for infrastructure
- ✅ Slow execution (1-10s per test)
- ✅ Regression testing

## Running Tests

### All Tests
```bash
pytest
```

### Unit Tests Only
```bash
pytest -m unit
```

### Integration Tests Only
```bash
pytest -m integration
```

### Specific Service
```bash
pytest services/api-service/tests/
```

### With Coverage Report
```bash
pytest --cov=services --cov-report=html
```

### Watch Mode (requires pytest-watch)
```bash
ptw
```

## Test Fixtures

### Common Fixtures

**conftest.py** provides shared fixtures:

```python
# tests/conftest.py
import pytest
from unittest.mock import Mock

@pytest.fixture
def mock_user_repository():
    """Mock repository for user tests"""
    return Mock()

@pytest.fixture
def mock_event_publisher():
    """Mock event publisher"""
    return Mock()

@pytest.fixture
def mock_mongodb():
    """Mocked MongoDB connection"""
    return Mock()
```

## Mocking Strategies

### Mocking Dependencies

```python
from unittest.mock import Mock, patch

# Create a mock
user_repo = Mock()
user_repo.find_by_email.return_value = None

# Or use patch for imports
@patch('services.api_service.infrastructure.persistence.UserRepository')
def test_with_patch(mock_repo):
    mock_repo.return_value.find_by_email.return_value = None
```

### Mocking External Services

```python
@patch('requests.get')
def test_external_service_call(mock_get):
    mock_get.return_value.json.return_value = {'status': 'ok'}
    
    # Your test code here
```

## Test Organization

### File Structure
```
service/tests/
├── unit/
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── entities/
│   │   │   └── test_*.py
│   │   └── services/
│   │       └── test_*.py
│   └── application/
│       └── test_*.py
├── integration/
│   ├── application/
│   │   └── test_*.py
│   └── infrastructure/
│       └── test_*.py
├── e2e/
│   └── test_*.py
├── conftest.py
└── fixtures/
    └── *.py
```

## Best Practices

1. **Test One Thing**: Each test should verify one behavior
2. **Clear Names**: Test names should describe what they test
3. **Arrange-Act-Assert**: Structure tests with setup, execution, verification
4. **No Test Dependencies**: Tests should run independently
5. **Mock External Calls**: Don't call real APIs or databases
6. **Fast Tests**: Unit tests should run in < 1ms
7. **Deterministic**: Tests should always produce same result
8. **Keep Fixtures Simple**: Don't overuse complex fixtures

## Continuous Integration

Tests run automatically on:
- Pre-commit (via pre-commit hooks)
- Pull requests
- Merges to main branch

See `.github/workflows/tests.yml` for CI configuration.

## Troubleshooting

### Tests Failing Locally

1. Ensure services are running: `docker-compose up -d`
2. Check `.env` file is correctly configured
3. Clear pytest cache: `pytest --cache-clear`
4. Run with verbose output: `pytest -vv`

### Coverage Not Detected

```bash
# Regenerate coverage
pytest --cov=services --cov-report=html --cov-erase
```

### Import Errors

```bash
# Reinstall dependencies
pip install -e ".[dev]"
```

## References

- [pytest Documentation](https://docs.pytest.org/)
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
