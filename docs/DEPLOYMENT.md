# Deployment Guide

## Overview

This guide covers deploying the AI-Enabled Distributed Backend Platform to production environments (Kubernetes) and staging environments.

## Prerequisites

- Docker & Docker Compose (for local builds)
- kubectl configured for your cluster
- Container registry credentials (Docker Hub, AWS ECR, Google GCR, etc.)
- Kubernetes cluster (1.24+)
- Helm (optional, for advanced deployments)

## Local Development

### Quick Start

```bash
# Clone repository
git clone <repository-url>
cd AI_MICROSERVICES

# Setup development environment
chmod +x scripts/dev/setup.sh
./scripts/dev/setup.sh

# Start services
chmod +x scripts/dev/start.sh
./scripts/dev/start.sh

# View logs
docker-compose logs -f
```

### Access Services

```
API Service: http://localhost:5000
Auth Service: http://localhost:5001
AI Worker: http://localhost:5002
Notification Service: http://localhost:5003
MongoDB: mongodb://admin:admin123@localhost:27017
RabbitMQ UI: http://localhost:15672 (guest/guest)
Flower (Celery): http://localhost:5555
```

## Building Docker Images

### Build Locally

```bash
# Build all services
docker-compose build

# Build specific service
docker-compose build api_service

# Build with no cache
docker-compose build --no-cache
```

### Build via Script

```bash
chmod +x scripts/deployment/build_images.sh
./scripts/deployment/build_images.sh
```

## Pushing to Registry

### Configuration

```bash
export REGISTRY=docker.io
export NAMESPACE=aiplatform
export VERSION=1.0.0
```

### Push Images

```bash
chmod +x scripts/deployment/push_images.sh
./scripts/deployment/push_images.sh
```

Or manually:

```bash
# Tag images
docker tag ai_platform_api_service:latest $REGISTRY/$NAMESPACE/api_service:$VERSION

# Push
docker push $REGISTRY/$NAMESPACE/api_service:$VERSION
```

## Kubernetes Deployment

### Prerequisites

1. Create namespace:
```bash
kubectl create namespace ai-platform
```

2. Create secrets for sensitive data:

```bash
# MongoDB credentials
kubectl create secret generic mongodb-credentials \
  --from-literal=username=admin \
  --from-literal=password=YOUR_SECURE_PASSWORD \
  -n ai-platform

# RabbitMQ credentials
kubectl create secret generic rabbitmq-credentials \
  --from-literal=username=guest \
  --from-literal=password=YOUR_SECURE_PASSWORD \
  -n ai-platform

# JWT secret
kubectl create secret generic jwt-secret \
  --from-literal=secret-key=YOUR_SECURE_JWT_KEY \
  -n ai-platform

# Registry credentials (if private)
kubectl create secret docker-registry regcred \
  --docker-server=$REGISTRY \
  --docker-username=YOUR_USERNAME \
  --docker-password=YOUR_PASSWORD \
  -n ai-platform
```

3. Create ConfigMap for configuration:

```bash
kubectl create configmap app-config \
  --from-file=config/environments/.env.staging \
  -n ai-platform
```

### Deploy to Kubernetes

```bash
# Apply all manifests
kubectl apply -f infrastructure/kubernetes/ -n ai-platform

# Verify deployment
kubectl get deployments -n ai-platform
kubectl get pods -n ai-platform
kubectl get services -n ai-platform

# Check logs
kubectl logs -f deployment/api_service -n ai-platform

# Port forward for testing
kubectl port-forward svc/api_service 5000:5000 -n ai-platform
```

### Monitor Deployment

```bash
# Watch pod status
kubectl get pods -w -n ai-platform

# Describe pod for issues
kubectl describe pod <pod-name> -n ai-platform

# View events
kubectl get events -n ai-platform
```

## Environment Configuration

### Development (.env.development)
```bash
cp config/environments/.env.development .env
docker-compose up -d
```

### Staging (.env.staging)
```bash
# Use managed services (AWS RDS, AWS MQ, etc.)
# Deploy with staging-specific Kubernetes manifests
kubectl apply -f infrastructure/kubernetes/staging/ -n ai-platform-staging
```

### Production (.env.production)
```bash
# All secrets managed by Kubernetes Secrets or cloud provider secrets manager
# Never commit production values to git
# Use certificate manager for TLS
# Configure auto-scaling policies
```

## Database Migration

### MongoDB Migrations

```bash
# Using database initialization
docker exec ai_platform_mongodb mongosh -u admin -p admin123 < scripts/db/init.js

# Or with Kubernetes
kubectl exec -it mongodb-0 -n ai-platform -- mongosh -u admin -p admin123
```

### Migration Script

```bash
# Coming soon: Alembic-like migration system for MongoDB
python scripts/deployment/migrate.py --version latest
```

## Monitoring and Logs

### Application Logs

```bash
# Docker Compose
docker-compose logs -f [service-name]

# Kubernetes
kubectl logs -f deployment/[service-name] -n ai-platform
```

### Metrics

Prometheus metrics available at:
```
http://localhost:9090/api/v1/query
```

### Health Checks

```bash
# API Service
curl http://localhost:5000/health

# Auth Service
curl http://localhost:5001/health

# Via Kubernetes
kubectl get endpoints -n ai-platform
```

## Scaling

### Manual Scaling

```bash
# Scale deployment
kubectl scale deployment api_service --replicas=3 -n ai-platform
```

### Auto-scaling

```bash
# Create HPA (Horizontal Pod Autoscaler)
kubectl autoscale deployment api_service --min=2 --max=10 --cpu-percent=80 -n ai-platform

# View HPA status
kubectl get hpa -n ai-platform
```

## Rollback

### Kubernetes Rollback

```bash
# View deployment history
kubectl rollout history deployment/api_service -n ai-platform

# Rollback to previous version
kubectl rollout undo deployment/api_service -n ai-platform

# Rollback to specific revision
kubectl rollout undo deployment/api_service --to-revision=2 -n ai-platform
```

### Docker Compose Rollback

```bash
# Pull previous image version
docker-compose pull --no-parallel

# Restart with previous version
docker-compose down
docker-compose up -d
```

## Troubleshooting

### Pod Fails to Start

```bash
# Check pod logs
kubectl logs <pod-name> -n ai-platform

# Describe pod for events
kubectl describe pod <pod-name> -n ai-platform

# Common issues:
# - Image not found: Verify registry and image tag
# - Insufficient resources: Check node resources
# - Readiness probe failed: Check application health
```

### Service Communication Issues

```bash
# Test connectivity between services
kubectl exec -it <pod-name> -n ai-platform -- curl http://api_service:5000/health

# Check DNS
kubectl exec -it <pod-name> -n ai-platform -- nslookup api_service
```

### Database Connection Issues

```bash
# Verify MongoDB is running
kubectl get statefulset mongodb -n ai-platform

# Check MongoDB logs
kubectl logs mongodb-0 -n ai-platform

# Test connection
kubectl exec -it <pod-name> -n ai-platform -- \
  mongosh mongodb://admin:password@mongodb:27017/ai_platform?authSource=admin
```

## Maintenance

### Update Services

```bash
# Blue-green deployment strategy
# 1. Deploy new version alongside current
kubectl set image deployment/api_service \
  api_service=registry/api_service:v2.0 -n ai-platform

# 2. Verify new version
kubectl get pods -n ai-platform

# 3. Switch traffic
kubectl get service api_service -n ai-platform

# 4. Remove old version
kubectl set image deployment/api_service \
  api_service=registry/api_service:v2.0 -n ai-platform
```

### Backup Data

```bash
# MongoDB backup
kubectl exec -it mongodb-0 -n ai-platform -- mongodump --uri="mongodb://admin:password@localhost:27017"

# Store in persistent storage or object storage (S3, GCS, etc.)
```

## Security

### Network Policies

```bash
# Restrict traffic between services
kubectl apply -f infrastructure/kubernetes/network-policies.yaml -n ai-platform
```

### RBAC (Role-Based Access Control)

```bash
# Create service account
kubectl create serviceaccount app-sa -n ai-platform

# Apply RBAC rules
kubectl apply -f infrastructure/kubernetes/rbac.yaml -n ai-platform
```

### TLS/HTTPS

```bash
# Using cert-manager
kubectl apply -f infrastructure/kubernetes/certificate.yaml -n ai-platform
```

## CI/CD Integration

### GitHub Actions

See `.github/workflows/deploy.yml` for automated deployment configuration.

### GitLab CI

See `.gitlab-ci.yml` for GitLab CI/CD configuration.

## Checklist Before Production

- [ ] All services have health checks configured
- [ ] Monitoring and alerts configured
- [ ] Database backups scheduled
- [ ] Secrets managed securely (not in git)
- [ ] Load balancer configured
- [ ] TLS certificates installed
- [ ] Rate limiting configured
- [ ] CORS policy set correctly
- [ ] Logging aggregation setup
- [ ] Disaster recovery plan in place

## Support

For deployment issues:
1. Check logs: `kubectl logs <pod-name> -n ai-platform`
2. Review events: `kubectl get events -n ai-platform`
3. Check resource usage: `kubectl top nodes`
4. Review architecture docs: `docs/ARCHITECTURE.md`
