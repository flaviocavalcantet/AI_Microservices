# Configuration Management Strategy

## Overview

This document outlines the configuration management strategy for the AI Microservices Platform. The strategy supports:

- **Multi-environment**: Development, Staging, Production, Testing
- **Cross-platform**: Windows, Linux, macOS
- **Framework-independent**: Configuration objects, not Flask-specific
- **Type-safe**: Pydantic for validation
- **Secrets-secure**: Sensitive data in environment variables, never committed
- **Docker-ready**: Works in containers and local development

## Configuration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Environment Variables / .env                   │
│  (.env, .env.development, .env.staging, .env.production)   │
└────────────────────────────────┬────────────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   python-dotenv load   │
                    │  Load environment vars │
                    └────────────┬────────────┘
                                 │
      ┌──────────────────────────▼──────────────────────────┐
      │   Config Loader (config.py)                         │
      │   - Determine environment                           │
      │   - Load appropriate Config class                   │
      │   - Validate with Pydantic                          │
      └──────────────────────────┬──────────────────────────┘
                                 │
    ┌────────────────────────────▼────────────────────────┐
    │   Typed Config Objects (BaseSettings)              │
    │   - Strongly typed attributes                       │
    │   - Built-in validation                             │
    │   - Environment variable mapping                    │
    └────────────────────────────┬────────────────────────┘
                                 │
    ┌────────────────────────────▼────────────────────────┐
    │   Application Code                                 │
    │   - Access config.DATABASE_URL                     │
    │   - Never reference os.environ directly            │
    └────────────────────────────────────────────────────┘
```

## Configuration Hierarchy

### Environment Variables (Highest Priority)

System environment variables override all other sources.

```bash
export FLASK_ENV=production
export DATABASE_URL=mongodb://...
export JWT_SECRET_KEY=your-secret
```

### .env Files (Second Priority)

Environment-specific files loaded by python-dotenv.

```bash
# Local machine
.env                    # Loaded first (gitignored)

# Or environment-specific
.env.development        # Development defaults
.env.staging           # Staging defaults
.env.production        # Production defaults (don't commit secrets!)
```

### Configuration Classes (Default/Fallback)

Python dataclasses with built-in defaults.

```python
class DevelopmentConfig:
    DATABASE_URL = "mongodb://localhost:27017/..."
    DEBUG = True
    LOG_LEVEL = "DEBUG"
```

## Configuration Structure

### Per-Service Configuration

Each service has its own configuration in `src/config.py`:

```
services/
├── api_service/
│   └── src/
│       ├── config.py          # API service configuration
│       └── main.py            # Load config and run
├── auth_service/
│   └── src/
│       ├── config.py          # Auth service configuration
│       └── main.py
├── ai_worker/
│   └── src/
│       ├── config.py          # Worker configuration
│       └── main.py
└── notification_service/
    └── src/
        ├── config.py          # Notification configuration
        └── main.py
```

### Shared Configuration

Common configuration base in `shared/`:

```
shared/
└── shared_config/
    ├── src/
    │   ├── __init__.py
    │   ├── base.py            # BaseSettings with common fields
    │   ├── validators.py      # Custom validation logic
    │   └── env_loader.py      # Load .env files
    └── requirements.txt
```

### Environment Files

```
config/
└── environments/
    ├── .env.example           # Template for all variables
    ├── .env.development       # Development defaults
    ├── .env.staging          # Staging defaults
    └── .env.production       # Production EXAMPLE (never commit real secrets!)
```

## Configuration Loading Strategy

### Single Source of Truth

Each service loads configuration exactly once during startup:

```python
# services/api_service/src/main.py
from services.api_service.src.config import get_config

def main():
    # Load configuration once at startup
    config = get_config()
    
    # Use config throughout application
    app = create_app(config)
    app.run()
```

### Environment Detection

Automatic environment detection with fallback:

```python
# Priority order:
# 1. FLASK_ENV environment variable
# 2. .env file in current directory
# 3. Default to 'development'

import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

env = os.getenv("FLASK_ENV", "development")
```

### Per-Environment Configuration

Different configuration for each environment:

```python
from pydantic import BaseSettings

class Settings(BaseSettings):
    """Base settings for all environments"""
    
    class Config:
        env_file = ".env"
        case_sensitive = True

class DevelopmentSettings(Settings):
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    DATABASE_URL: str = "mongodb://localhost:27017/..."

class ProductionSettings(Settings):
    DEBUG: bool = False
    LOG_LEVEL: str = "WARNING"
    DATABASE_URL: str  # Required from environment

def get_config() -> Settings:
    env = os.getenv("FLASK_ENV", "development")
    if env == "production":
        return ProductionSettings()
    return DevelopmentSettings()
```

## Environment Variables by Service

### API Service

```env
# Environment
FLASK_ENV=development
SERVICE_NAME=api_service
SERVICE_PORT=5000
SERVICE_HOST=0.0.0.0

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Database
MONGODB_URI=mongodb://admin:admin123@localhost:27017/api_service?authSource=admin

# Message Queue
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Cache
REDIS_URL=redis://localhost:6379/0

# Security
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000

# API Documentation
SWAGGER_ENABLED=true
OPENAPI_VERSION=3.0.3
```

### Auth Service

```env
# Environment
FLASK_ENV=development
SERVICE_NAME=auth_service
SERVICE_PORT=5001

# Logging
LOG_LEVEL=INFO

# Database
MONGODB_URI=mongodb://admin:admin123@localhost:27017/auth_service?authSource=admin

# Message Queue
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Security
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
PASSWORD_HASHING_ALGORITHM=bcrypt

# Email (optional, for password reset)
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USER=your-email@gmail.com
EMAIL_SMTP_PASSWORD=your-app-password
```

### AI Worker

```env
# Environment
FLASK_ENV=development
SERVICE_NAME=ai_worker
SERVICE_PORT=5002

# Logging
LOG_LEVEL=INFO

# Database
MONGODB_URI=mongodb://admin:admin123@localhost:27017/ai_worker?authSource=admin

# Message Queue
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Cache
REDIS_URL=redis://localhost:6379/1

# Celery
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672/
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# ML/AI Configuration
MODEL_CACHE_DIR=/tmp/ai_worker_cache
MAX_WORKERS=4
GPU_ENABLED=false
GPU_DEVICE=cuda:0
```

### Notification Service

```env
# Environment
FLASK_ENV=development
SERVICE_NAME=notification_service
SERVICE_PORT=5003

# Logging
LOG_LEVEL=INFO

# Database
MONGODB_URI=mongodb://admin:admin123@localhost:27017/notification_service?authSource=admin

# Message Queue
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Celery
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672/
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Email Configuration
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USER=notifications@company.com
EMAIL_SMTP_PASSWORD=your-app-password
EMAIL_FROM_ADDRESS=notifications@company.com
EMAIL_FROM_NAME=AI Platform

# SMS Configuration (optional)
SMS_PROVIDER=twilio
SMS_ACCOUNT_SID=your-account-sid
SMS_AUTH_TOKEN=your-auth-token
SMS_FROM_NUMBER=+1234567890

# Push Notifications (optional)
PUSH_PROVIDER=firebase
PUSH_SERVICE_ACCOUNT_KEY=/path/to/serviceAccountKey.json
```

## Cross-Platform Considerations

### Windows-Specific

```bash
# PowerShell - Set environment variable
$env:FLASK_ENV = "development"

# Batch - Set environment variable
set FLASK_ENV=development

# Or use .env file (recommended)
# Works automatically with python-dotenv
```

### Linux/macOS

```bash
# Bash - Set environment variable
export FLASK_ENV=development

# Or in ~/.bashrc or ~/.zshrc for persistence
echo 'export FLASK_ENV=development' >> ~/.bashrc

# Or use .env file (recommended)
```

### Docker

```dockerfile
# Set environment variables in Dockerfile
ENV FLASK_ENV=production
ENV LOG_LEVEL=WARNING

# Or pass at runtime
docker run -e FLASK_ENV=production ...

# Or use --env-file
docker run --env-file .env.production ...
```

## Secrets Management Best Practices

### 1. Never Commit Secrets

```bash
# .gitignore - prevent accidental commits
.env                    # Local environment variables
.env.*.local           # Local environment overrides
.env.production        # Production should never be committed

# Only commit examples
.env.example           # Template
.env.development       # Safe defaults (no real secrets)
```

### 2. Use Environment Variables

```python
# GOOD: Read from environment
secret_key = os.getenv("JWT_SECRET_KEY")
if not secret_key:
    raise ValueError("JWT_SECRET_KEY environment variable must be set")

# BAD: Hardcode secrets
secret_key = "my-secret-key"  # Never do this!
```

### 3. Different Secrets per Environment

```env
# .env.development (can be committed)
JWT_SECRET_KEY=dev-secret-key-only-for-testing

# .env.production (NEVER commit)
JWT_SECRET_KEY=production-secret-from-secrets-manager

# Use secrets manager in production:
# - AWS Secrets Manager
# - HashiCorp Vault
# - Azure Key Vault
# - Kubernetes Secrets
```

### 4. Validate Required Secrets

```python
class ProductionConfig(BaseSettings):
    """Production configuration - require all secrets"""
    
    JWT_SECRET_KEY: str
    
    def __init__(self, **data):
        super().__init__(**data)
        
        # Validate secret length
        if len(self.JWT_SECRET_KEY) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters in production")
        
        # Validate it's not the development value
        if self.JWT_SECRET_KEY == "dev-secret-key-only-for-testing":
            raise ValueError("Using development secret key in production!")
```

## Configuration Loading Examples

### Development Setup

```bash
# 1. Copy template
cp config/environments/.env.example .env

# 2. Edit .env (only local, gitignored)
# Add your local development settings

# 3. Run application
python -m services.api_service.src.main
# Automatically loads .env in current directory
```

### Testing Setup

```python
# tests/conftest.py
import os
import pytest
from dotenv import load_dotenv

@pytest.fixture(scope="session", autouse=True)
def load_test_config():
    """Load test configuration before running tests"""
    load_dotenv("config/environments/.env.testing")

# Tests now have consistent configuration
```

### Docker Setup

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Copy application
COPY . .

# Install dependencies
RUN pip install -r requirements.txt

# Set environment variables
ENV FLASK_ENV=production
ENV LOG_LEVEL=WARNING

# Load .env.production from docker run or build args
# docker build --build-arg ENV_FILE=.env.production
# docker run --env-file .env.production ...

EXPOSE 5000
CMD ["python", "-m", "services.api_service.src.main"]
```

### Docker Compose Setup

```yaml
# docker-compose.yml
services:
  api_service:
    build: .
    environment:
      FLASK_ENV: development
      LOG_LEVEL: DEBUG
      MONGODB_URI: mongodb://admin:admin123@mongodb:27017/api_service
      RABBITMQ_URL: amqp://guest:guest@rabbitmq:5672/
    # Or load from file:
    env_file:
      - config/environments/.env.development
    ports:
      - "5000:5000"
```

### Production Deployment

```bash
# 1. Set environment variables in cluster/cloud platform
# AWS: Parameter Store or Secrets Manager
# Kubernetes: Secrets and ConfigMaps
# Heroku: Config Vars
# GCP: Secret Manager

# 2. Application loads from environment
config = get_config()  # Reads from environment

# 3. Never need to commit production .env file
# Production secrets come from cluster/cloud infrastructure
```

## Configuration Validation

### Startup Validation

```python
# services/api_service/src/main.py
def main():
    try:
        # Load and validate configuration
        config = get_config()
        
        # Configuration is validated here by Pydantic
        logger.info(f"Configuration loaded for environment: {config.FLASK_ENV}")
        
        # Check required services are accessible
        if not validate_database_connection(config):
            logger.error("Cannot connect to database")
            sys.exit(1)
        
        if not validate_message_queue(config):
            logger.error("Cannot connect to message queue")
            sys.exit(1)
        
        # All good - run application
        app = create_app(config)
        app.run()
    
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
```

### Health Check

```python
# services/api_service/src/presentation/routes/health.py
@app.route("/health/config", methods=["GET"])
def config_health():
    """Health check endpoint showing configuration status"""
    
    response = {
        "status": "healthy",
        "environment": current_app.config.get("FLASK_ENV"),
        "debug": current_app.config.get("DEBUG"),
        "logging": {
            "level": current_app.config.get("LOG_LEVEL"),
            "format": current_app.config.get("LOG_FORMAT"),
        },
        "services": {
            "database": check_database(),
            "message_queue": check_rabbitmq(),
            "cache": check_redis(),
        }
    }
    
    return jsonify(response)
```

## Configuration Reloading

### Development: Auto-reload on .env changes

```bash
# Use environment-aware development servers
# Flask with FLASK_ENV=development auto-reloads

# Or use watchdog to monitor .env
pip install python-watchdog
watchmedo auto-restart -d . -p '*.py;.env' -- python -m services.api_service.src.main
```

### Production: No reload (immutable config)

Configuration is loaded once at startup and never reloaded.

For configuration updates in production:
1. Update secrets manager/environment
2. Deploy new container with `docker pull` and `docker run`
3. Old container stops gracefully
4. New container starts with new configuration

## Configuration Debugging

### Print Current Configuration

```python
# Development utility to see active configuration
def print_config(config: BaseSettings):
    """Print configuration for debugging (safe values only)"""
    
    config_dict = config.dict()
    
    # Mask sensitive values
    sensitive_keys = ["password", "secret", "token", "key", "credential"]
    
    for key, value in config_dict.items():
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            print(f"{key}: *** (hidden)")
        else:
            print(f"{key}: {value}")

# Usage
from services.api_service.src.config import get_config
config = get_config()
print_config(config)
```

### Environment Variables in Use

```bash
# See what environment variables are active
python -c "import os; print(os.environ)" | grep -E "FLASK|MONGODB|RABBITMQ|JWT"

# Or in Python
import os
for key, value in os.environ.items():
    if any(x in key.upper() for x in ['FLASK', 'MONGODB', 'RABBITMQ', 'JWT']):
        print(f"{key}: {value}")
```

## Checklist: Configuration Setup

- [ ] Create shared configuration base (pydantic BaseSettings)
- [ ] Each service has config.py with environment-specific classes
- [ ] .env files created from .env.example template
- [ ] .env files added to .gitignore (never commit secrets)
- [ ] Environment detection working (FLASK_ENV, PYTHONENV)
- [ ] Secrets validated at startup (fail fast if missing)
- [ ] Configuration works on Windows and Linux
- [ ] Docker .env file mapping configured
- [ ] docker-compose environment setup works
- [ ] Logging shows active environment at startup
- [ ] Production requires environment variables (not defaults)
- [ ] Configuration documented in README

## References

- [python-dotenv Documentation](https://github.com/theskumar/python-dotenv)
- [Pydantic BaseSettings](https://pydantic-docs.helpmanual.io/usage/settings/)
- [12-Factor App - Config](https://12factor.net/config)
- [Environment Variables Best Practices](https://stackoverflow.com/questions/3290424/python-script-to-store-secrets)
