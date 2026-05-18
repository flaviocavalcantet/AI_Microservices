# API Specification

## Overview

This document specifies the REST API contracts for the AI-Enabled Distributed Backend Platform.

## Base URLs

- **Development**: `http://localhost:5000`
- **Staging**: `https://api-staging.company.com`
- **Production**: `https://api.company.com`

## Authentication

All endpoints (except `/auth/login` and `/auth/register`) require JWT Bearer token:

```
Authorization: Bearer <jwt_token>
```

## Response Format

### Success Response (2xx)

```json
{
  "status": "success",
  "data": { /* endpoint-specific data */ },
  "timestamp": "2026-05-15T10:30:00Z"
}
```

### Error Response (4xx, 5xx)

```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": { /* additional error information */ }
  },
  "timestamp": "2026-05-15T10:30:00Z"
}
```

## Endpoints

### Authentication Service

#### Register User

```
POST /auth/register
```

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securePassword123",
  "name": "John Doe"
}
```

**Response (201):**
```json
{
  "status": "success",
  "data": {
    "user_id": "user_123",
    "email": "user@example.com",
    "name": "John Doe",
    "created_at": "2026-05-15T10:30:00Z"
  }
}
```

#### Login

```
POST /auth/login
```

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGc...",
    "refresh_token": "eyJhbGc...",
    "expires_in": 3600,
    "user": {
      "user_id": "user_123",
      "email": "user@example.com",
      "name": "John Doe"
    }
  }
}
```

#### Refresh Token

```
POST /auth/refresh
```

**Request:**
```json
{
  "refresh_token": "eyJhbGc..."
}
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGc...",
    "expires_in": 3600
  }
}
```

### API Service

#### Create Processing Request

```
POST /api/v1/requests
```

**Request:**
```json
{
  "title": "Process data",
  "input_data": { /* arbitrary JSON */ },
  "priority": "high"
}
```

**Response (201):**
```json
{
  "status": "success",
  "data": {
    "request_id": "req_456",
    "title": "Process data",
    "status": "pending",
    "created_at": "2026-05-15T10:30:00Z"
  }
}
```

#### Get Request Status

```
GET /api/v1/requests/{request_id}
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "request_id": "req_456",
    "title": "Process data",
    "status": "processing",
    "progress": 45,
    "created_at": "2026-05-15T10:30:00Z",
    "started_at": "2026-05-15T10:31:00Z"
  }
}
```

#### List Requests

```
GET /api/v1/requests?page=1&limit=20&status=processing
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "items": [ /* request objects */ ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 100,
      "pages": 5
    }
  }
}
```

### Health Check

```
GET /health
```

**Response (200):**
```json
{
  "status": "healthy",
  "service": "api_service",
  "version": "1.0.0",
  "timestamp": "2026-05-15T10:30:00Z",
  "dependencies": {
    "mongodb": "healthy",
    "rabbitmq": "healthy",
    "auth_service": "healthy"
  }
}
```

## Error Codes

| Code | Status | Description |
|------|--------|-------------|
| VALIDATION_ERROR | 400 | Input validation failed |
| UNAUTHORIZED | 401 | Missing or invalid authentication |
| FORBIDDEN | 403 | Insufficient permissions |
| NOT_FOUND | 404 | Resource not found |
| CONFLICT | 409 | Resource already exists |
| RATE_LIMITED | 429 | Too many requests |
| INTERNAL_ERROR | 500 | Internal server error |
| SERVICE_UNAVAILABLE | 503 | Service temporarily unavailable |

## Rate Limiting

- **Limit**: 1000 requests per minute per IP
- **Headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

## Pagination

Query parameters for paginated endpoints:
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 20, max: 100)
- `sort`: Sort field (default: created_at)
- `order`: Sort order (asc or desc)

## Versioning

API version specified in URL path: `/api/v1/...`

Current version: `v1`

## Changelog

### v1.0.0 (2026-05-15)
- Initial release
- Authentication endpoints
- Request management endpoints
- Health check endpoint

## Support

For API issues or questions, contact api-support@company.com
