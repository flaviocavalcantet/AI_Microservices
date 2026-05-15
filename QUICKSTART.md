# Quick Reference Guide

## Project Overview

**AI-Enabled Distributed Backend Platform** — Production-grade microservices architecture with Python 3.12+, Flask, MongoDB, RabbitMQ, Celery, and Clean Architecture principles.

## Directory Structure Overview

```
AI_MICROSERVICES/
├── services/                    # Microservices
│   ├── api-service/            # API gateway
│   ├── auth-service/           # Authentication
│   ├── ai-worker/              # AI processing
│   └── notification-service/   # Notifications
├── shared/                      # Shared libraries
│   ├── shared-kernel/          # Core abstractions
│   ├── shared-events/          # Event definitions
│   └── shared-utils/           # Utilities
├── infrastructure/              # Docker & Kubernetes
├── scripts/                     # Developer tools
├── docs/                        # Documentation
├── config/                      # Configuration
└── docker-compose.yml          # Local development
```

## Architecture Layers (Per Service)

```
domain/              → Pure business logic (framework-independent)
application/         → Use cases and orchestration
infrastructure/      → Database, messaging, external services
presentation/        → HTTP routes and middleware
```

## Quick Start

```bash
# 1. Setup environment
./scripts/dev/setup.sh

# 2. Start services
./scripts/dev/start.sh

# 3. View logs
docker-compose logs -f

# 4. Run tests
pytest

# 5. Stop services
./scripts/dev/stop.sh
```

## Service Access

| Service | URL | Port |
|---------|-----|------|
| API | http://localhost:5000 | 5000 |
| Auth | http://localhost:5001 | 5001 |
| AI Worker | http://localhost:5002 | 5002 |
| Notifications | http://localhost:5003 | 5003 |
| MongoDB | localhost:27017 | 27017 |
| RabbitMQ | localhost:5672 | 5672 |
| RabbitMQ UI | http://localhost:15672 | 15672 |
| Flower (Celery) | http://localhost:5555 | 5555 |

## Common Commands

### Development

```bash
# Activate venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Run specific service
python -m services.api_service.main

# Database shell
docker-compose exec mongodb mongosh

# RabbitMQ shell
docker-compose exec rabbitmq rabbitmq-ctl status
```

### Testing

```bash
# All tests
pytest

# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Specific service
pytest services/api-service/tests

# With coverage
pytest --cov=services --cov-report=html

# Watch mode
ptw
```

### Docker

```bash
# Build services
docker-compose build

# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f [service]

# Execute command in container
docker-compose exec [service] [command]
```

### Code Quality

```bash
# Format code
black services shared

# Sort imports
isort services shared

# Lint
flake8 services shared

# Type check
mypy services shared --ignore-missing-imports
```

### Deployment

```bash
# Build images
./scripts/deployment/build_images.sh

# Push images
./scripts/deployment/push_images.sh

# Deploy to Kubernetes
kubectl apply -f infrastructure/kubernetes/ -n ai-platform
```

## Key Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Local development orchestration |
| `pyproject.toml` | Project metadata and tool config |
| `requirements.txt` | Root dependencies |
| `.env.example` | Environment variables template |
| `README.md` | Project overview |
| `docs/ARCHITECTURE.md` | Architecture decisions |
| `docs/STRUCTURE.md` | Project structure guide |
| `docs/TESTING.md` | Testing strategy |
| `docs/DEPLOYMENT.md` | Deployment procedures |

## Naming Conventions

### Files
- Entities: `user.py`
- Repositories: `user_repository.py`
- Use Cases: `create_user_use_case.py`
- DTOs: `create_user_request.py`
- Routes: `user_routes.py`
- Tests: `test_user.py`

### Classes
- Entities: `User`, `Request`
- Repositories: `IUserRepository`, `MongoUserRepository`
- Use Cases: `CreateUserUseCase`
- DTOs: `CreateUserRequest`, `UserResponse`
- Exceptions: `UserAlreadyExistsException`

## Design Principles

1. **Clean Architecture**: Layers, dependency rule, testability
2. **Domain-Driven Design**: Ubiquitous language, bounded contexts
3. **Event-Driven**: Async communication via RabbitMQ
4. **SOLID Principles**: Single responsibility, Open/closed, etc.
5. **12-Factor App**: Configuration, logging, stateless services

## Environment Variables

Key variables to configure:

```env
# Services
FLASK_ENV=development
LOG_LEVEL=INFO

# Database
MONGODB_URI=mongodb://admin:admin123@localhost:27017/ai_platform

# Messaging
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Authentication
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256

# Email
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_USER=your-email@gmail.com
```

## Development Workflow

1. **Create branch**: `git checkout -b feature/name`
2. **Write tests**: `tests/unit/` for business logic
3. **Implement code**: Follow architecture layers
4. **Run tests**: `pytest`
5. **Format code**: `black` and `isort`
6. **Commit**: `git commit -m "type(scope): message"`
7. **Push**: `git push origin feature/name`
8. **PR**: Create pull request with description

## Git Workflow

```bash
# Create feature branch
git checkout -b feature/my-feature

# Make changes
git add .
git commit -m "feat(api-service): add user endpoint"

# Push to remote
git push origin feature/my-feature

# Create PR and get reviews
# After approval, merge to main
```

## Troubleshooting

### Services Won't Start
```bash
# Check logs
docker-compose logs -f

# Check port conflicts
lsof -i :5000  # Check if port 5000 is in use

# Rebuild
docker-compose build --no-cache
```

### Tests Failing
```bash
# Clear cache
pytest --cache-clear

# Run with verbose output
pytest -vv

# Run specific test
pytest services/api-service/tests/test_file.py::TestClass::test_method
```

### Import Errors
```bash
# Reinstall dependencies
pip install -e ".[dev]"

# Verify Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Database Issues
```bash
# Reset MongoDB
docker-compose down -v
docker-compose up -d mongodb

# Connect to MongoDB
docker-compose exec mongodb mongosh
```

## Useful Links

- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Domain-Driven Design](https://martinfowler.com/bliki/DomainDrivenDesign.html)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [MongoDB Documentation](https://docs.mongodb.com/)
- [RabbitMQ Documentation](https://www.rabbitmq.com/documentation.html)
- [Celery Documentation](https://docs.celeryproject.io/)
- [pytest Documentation](https://docs.pytest.org/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)

## Support

- **Docs**: `docs/` folder
- **Issues**: GitHub Issues
- **Chat**: Team Slack channel
- **Email**: team@aiplatform.local

## Next Steps

1. Read [ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design
2. Review [STRUCTURE.md](docs/STRUCTURE.md) for code organization
3. Check [TESTING.md](docs/TESTING.md) for test strategies
4. Read [DEPLOYMENT.md](docs/DEPLOYMENT.md) for production deployment
5. Review [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines

---

**Last Updated**: 2026-05-15  
**Version**: 1.0.0
