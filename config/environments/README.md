# Environment Configuration Guide

This directory contains environment-specific configuration files for the AI Microservices platform.

## Files

- **`.env.example`** - Template with all available configuration options and explanations
- **`.env.development`** - Development environment (local machine)
- **`.env.staging`** - Staging environment (pre-production)
- **`.env.production`** - Production environment (NEVER commit with real secrets)

## Setup Instructions

### 1. Local Development

Copy the development configuration to your project root:

```bash
# Option A: Copy directly
cp config/environments/.env.development .env

# Option B: Start from example and customize
cp config/environments/.env.example .env
# Edit .env with your local settings
```

Then start your services:

```bash
# Using docker-compose
docker-compose up

# Or run Flask app directly
export FLASK_ENV=development
python -m services.api_service.src.main
```

### 2. Staging Environment

1. Copy staging template:
```bash
cp config/environments/.env.staging .env.staging
```

2. Replace placeholder values with actual staging service URLs

3. **IMPORTANT**: Keep `JWT_SECRET_KEY=SET_VIA_ENVIRONMENT_OR_SECRETS_MANAGER`
   - Real secrets will be injected via environment variables during deployment

4. Deploy with environment variable override:
```bash
# Via docker-compose
docker-compose --env-file .env.staging up

# Via Kubernetes
kubectl apply -f infrastructure/kubernetes/api_service-staging.yaml
```

### 3. Production Environment

**⚠️ CRITICAL SECURITY RULES:**

1. **NEVER commit `.env.production` with real secrets to version control**
2. **NEVER hardcode secrets in code or configuration files**
3. **NEVER expose production `.env` files in logs or error messages**

Production secrets must come from:
- **Kubernetes Secrets**: For Kubernetes deployments
- **AWS Secrets Manager**: For AWS deployments
- **Azure Key Vault**: For Azure deployments
- **Environment variables**: Set by CI/CD pipeline or deployment system

#### Kubernetes Deployment Example

```bash
# 1. Create a Kubernetes secret with production values
kubectl create secret generic api_service-secrets \
  --from-literal=MONGODB_URI='mongodb://user:pass@prod-mongodb:27017/api_service?authSource=admin' \
  --from-literal=RABBITMQ_URL='amqp://user:pass@prod-rabbitmq:5672/' \
  --from-literal=REDIS_URL='redis://:pass@prod-redis:6379/0' \
  --from-literal=JWT_SECRET_KEY='<generate-secure-random-key>' \
  -n production

# 2. Reference in deployment spec (see infrastructure/kubernetes/)
# env:
#   - name: MONGODB_URI
#     valueFrom:
#       secretKeyRef:
#         name: api_service-secrets
#         key: MONGODB_URI
```

#### Generate Secure JWT Secret

```bash
# Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Linux/Mac
openssl rand -base64 32
```

## Configuration Hierarchy

Environment variables are loaded in this priority order (highest to lowest):

1. **Environment variables** (set in shell or Kubernetes)
2. **`.env`** file (local override, never committed)
3. **`.env.{FLASK_ENV}`** file (environment-specific template)
4. **Defaults** in code (fallback values)

### Example: Loading Configuration

```python
# In your Flask app
from shared.shared_config import get_settings, load_env

# Load environment variables from .env files
load_env()

# Get settings for current environment (detects FLASK_ENV)
settings = get_settings()

# Access configuration
print(settings.MONGODB_URI)
print(settings.LOG_LEVEL)
print(settings.JWT_SECRET_KEY)  # Keep this private!
```

## Variables Reference

### Core Environment Variables

| Variable | Required | Development | Staging | Production |
|----------|----------|-------------|---------|------------|
| `FLASK_ENV` | Yes | development | staging | production |
| `SERVICE_NAME` | Yes | api_service | api_service | api_service |
| `SERVICE_PORT` | Yes | 5000 | 5000 | 5000 |
| `LOG_LEVEL` | Yes | DEBUG | INFO | WARNING |
| `LOG_FORMAT` | Yes | text | json | json |

### Database

| Variable | Required | Format | Notes |
|----------|----------|--------|-------|
| `MONGODB_URI` | Yes | `mongodb://user:pass@host:port/db?authSource=admin` | Include auth source |
| | | Development | `mongodb://admin:admin123@localhost:27017/api_service?authSource=admin` |
| | | Production | Set via Kubernetes Secret or secrets manager |

### Message Queue (RabbitMQ)

| Variable | Required | Format | Notes |
|----------|----------|--------|-------|
| `RABBITMQ_URL` | Yes | `amqp://user:pass@host:port/` | Include trailing slash |

### Caching (Redis)

| Variable | Required | Format | Notes |
|----------|----------|--------|-------|
| `REDIS_URL` | Yes | `redis://:pass@host:port/db` | Include database number |

### Security

| Variable | Required | Min Length | Algorithm |
|----------|----------|-----------|-----------|
| `JWT_SECRET_KEY` | Yes | 32 chars (production) | HS256 or RS256 |
| `JWT_ALGORITHM` | No | N/A | Default: HS256 |
| `JWT_EXPIRATION_HOURS` | No | N/A | Default: 24 |

### CORS

| Variable | Required | Format | Example |
|----------|----------|--------|---------|
| `CORS_ALLOWED_ORIGINS` | No | Comma-separated URLs | `http://localhost:3000,http://localhost:8000` |

## Best Practices

### 1. Development

- Use `.env.development` template
- Never commit real credentials
- Use localhost/docker hostnames
- Enable debug logging for troubleshooting

### 2. Staging

- Mirror production configuration structure
- Use staging service URLs and databases
- Keep `SET_VIA_ENVIRONMENT_OR_SECRETS_MANAGER` placeholders for secrets
- Test with realistic data volumes

### 3. Production

- **Zero secrets in committed files**
- Use secrets manager (Kubernetes/AWS/Azure)
- Validate all required variables at startup
- Use strong, random JWT secrets (32+ characters)
- Minimal logging (WARNING level)
- Disable Swagger/API documentation

### 4. Testing

```python
# tests/conftest.py
import os
os.environ['FLASK_ENV'] = 'testing'

from shared.shared_config import get_settings
settings = get_settings()

# settings will use TestingSettings with test database
```

## Troubleshooting

### "Missing required configuration: JWT_SECRET_KEY"

**Problem**: JWT_SECRET_KEY not set in environment

**Solution**:
```bash
# Development: Edit .env file
echo "JWT_SECRET_KEY=dev-secret-key-only-for-testing" >> .env

# Production: Set via Kubernetes Secret
kubectl set env pod/api_service JWT_SECRET_KEY='<new-value>' -n production
```

### "FLASK_ENV not recognized: 'production'"

**Problem**: Invalid FLASK_ENV value

**Solution**: Valid values are: `development`, `staging`, `production`, `testing`

```bash
export FLASK_ENV=production
```

### "Cannot connect to MongoDB: Connection refused"

**Problem**: MongoDB URI incorrect or service not running

**Solution**:
```bash
# Check MongoDB is running
docker-compose ps

# Verify connection string in .env
cat .env | grep MONGODB_URI

# Test connection
python -c "from pymongo import MongoClient; MongoClient('mongodb://...').server_info()"
```

### "JWT_SECRET_KEY must be at least 32 characters in production"

**Problem**: Weak JWT secret in production environment

**Solution**:
```bash
# Generate strong key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set in Kubernetes Secret or environment variable
export JWT_SECRET_KEY='<generated-key>'
```

## Configuration Validation

Configuration is validated at application startup. If any required variables are missing or invalid, the application will fail with a clear error message:

```python
# Automatic validation happens when getting settings
from shared.shared_config import get_settings

try:
    settings = get_settings()
except ValueError as e:
    print(f"Configuration error: {e}")
    exit(1)
```

## Cross-Platform Considerations

### Windows PowerShell

```powershell
# Set environment variable
$env:FLASK_ENV = "development"

# Load .env file with python-dotenv
python -c "from dotenv import load_dotenv; load_dotenv()"
```

### Linux/Mac Bash

```bash
# Set environment variable
export FLASK_ENV=development

# Source .env file
set -a
source .env
set +a
```

### Docker

```bash
# Pass environment file to container
docker run --env-file .env.development <image>

# Or set individual variables
docker run -e FLASK_ENV=production -e JWT_SECRET_KEY='...' <image>
```

### Docker Compose

```yaml
# docker-compose.yml
services:
  api_service:
    image: ai-microservices/api_service:latest
    env_file:
      - config/environments/.env.development
    environment:
      - FLASK_ENV=development  # Override if needed
```

## Further Reading

- [Pydantic Settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [python-dotenv Documentation](https://github.com/theskumar/python-dotenv)
- [Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [AWS Secrets Manager](https://aws.amazon.com/secrets-manager/)
- [Azure Key Vault](https://learn.microsoft.com/en-us/azure/key-vault/)
