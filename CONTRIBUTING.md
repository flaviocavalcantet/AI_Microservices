# Contributing Guidelines

## Code of Conduct

All contributors must follow professional standards and treat colleagues respectfully.

## Getting Started

1. **Fork** the repository
2. **Clone** locally: `git clone <your-fork-url>`
3. **Create** feature branch: `git checkout -b feature/your-feature`
4. **Setup** development environment: `./scripts/dev/setup.sh`
5. **Make** your changes
6. **Test** thoroughly: `pytest`
7. **Commit** with clear messages
8. **Push** to your fork
9. **Submit** pull request

## Coding Standards

### Python Style

- Follow PEP 8 with Black formatter
- Line length: 100 characters
- Use type hints on all public APIs
- Comprehensive docstrings for public methods

### Formatting

```bash
# Format code
black services shared

# Sort imports
isort services shared

# Check style
flake8 services shared
```

### Type Checking

```bash
# Run mypy
mypy services shared --ignore-missing-imports
```

## Commit Convention

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

**Scopes**: `api_service`, `auth_service`, `ai_worker`, `notification_service`, `shared_kernel`

**Example:**
```
feat(api_service): add pagination to requests endpoint

- Implement limit and offset parameters
- Add validation for pagination values
- Update documentation

Closes #123
```

## Testing

Write tests for all changes:

```bash
# Run all tests
pytest

# With coverage
pytest --cov=services --cov=shared

# Specific test
pytest services/api_service/tests/unit/domain/test_user.py -v
```

## Pull Request Process

1. **Title**: Clear, concise, follows commit convention
2. **Description**: What and why, not how
3. **Tests**: All tests pass
4. **Coverage**: New code has tests
5. **Documentation**: Update relevant docs
6. **Reviewers**: Request 2 approvals minimum

## Architecture Guidelines

### Clean Architecture Layers

- **Domain**: Pure business logic, no dependencies
- **Application**: Orchestration and use cases
- **Infrastructure**: Technical implementations
- **Presentation**: HTTP layer

Dependencies flow inward. Domain has no external dependencies.

### Service Boundaries

- **api_service**: Orchestration and API gateway
- **auth_service**: Authentication and authorization
- **ai_worker**: AI/ML processing
- **notification_service**: Asynchronous notifications

Services communicate via:
- **RabbitMQ**: Event-driven asynchronous
- **HTTP**: Synchronous service-to-service
- **Not directly through database**

### Code Organization

```
service/
├── domain/           # Pure business logic
├── application/      # Use cases and DTOs
├── infrastructure/   # Database and external services
├── presentation/     # HTTP routes and middleware
└── tests/           # Mirrored test structure
```

## Documentation

Update docs for:
- New features
- API changes
- Architecture decisions
- Configuration changes

Docs location:
- `docs/ARCHITECTURE.md` - Architecture decisions
- `docs/STRUCTURE.md` - Project structure
- `docs/API_SPECIFICATION.md` - API endpoints
- `docs/DEPLOYMENT.md` - Deployment procedures
- `README.md` - Quick reference

## Performance Considerations

- Prefer async operations for I/O
- Use connection pooling for databases
- Cache frequently accessed data
- Batch operations when possible
- Monitor query performance

## Security

- Never commit secrets or credentials
- Use environment variables for configuration
- Validate all inputs
- Sanitize outputs
- Use HTTPS in production
- Implement rate limiting

## Questions?

- Check existing docs and code
- Review architecture decisions in `docs/ARCHITECTURE.md`
- Ask in team chat or create a discussion issue

Thank you for contributing!
