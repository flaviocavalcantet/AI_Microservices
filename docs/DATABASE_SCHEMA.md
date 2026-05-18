# Database Schema

## Overview

The platform uses MongoDB as the primary datastore. This document describes the database schema design and collection structure.

## Collections

### auth_service.users

Stores user accounts and authentication data.

```json
{
  "_id": ObjectId,
  "email": "user@example.com",
  "username": "john_doe",
  "password_hash": "bcrypt_hash",
  "full_name": "John Doe",
  "is_active": true,
  "role": "user",  // admin, user, guest
  "permissions": ["read", "write"],
  "profile_data": {
    "avatar_url": "https://...",
    "bio": "Software engineer"
  },
  "created_at": ISODate("2026-05-15T10:30:00Z"),
  "updated_at": ISODate("2026-05-15T10:30:00Z"),
  "last_login_at": ISODate("2026-05-15T10:30:00Z")
}
```

**Indexes:**
- `email` (unique)
- `username` (unique)
- `created_at` (for sorting)

### auth_service.refresh_tokens

Stores refresh tokens for session management.

```json
{
  "_id": ObjectId,
  "user_id": ObjectId,  // Reference to users
  "token_hash": "sha256_hash",
  "expires_at": ISODate("2026-05-22T10:30:00Z"),
  "created_at": ISODate("2026-05-15T10:30:00Z"),
  "revoked": false
}
```

**Indexes:**
- `user_id`
- `expires_at` (TTL index for automatic cleanup)

### api_service.requests

Stores user requests for processing.

```json
{
  "_id": ObjectId,
  "user_id": ObjectId,  // Reference to users
  "title": "Analyze customer data",
  "description": "Analyze Q1 customer behavior",
  "input_data": { /* arbitrary JSON */ },
  "output_data": { /* result from ai_worker */ },
  "status": "processing",  // pending, processing, completed, failed
  "priority": "high",  // low, medium, high
  "error_message": null,
  "progress_percentage": 45,
  "estimated_completion_time": ISODate("2026-05-15T11:00:00Z"),
  "created_at": ISODate("2026-05-15T10:30:00Z"),
  "started_at": ISODate("2026-05-15T10:31:00Z"),
  "completed_at": null,
  "processing_time_ms": 1500,
  "metadata": {
    "source": "api",
    "client_ip": "192.168.1.1"
  }
}
```

**Indexes:**
- `user_id`
- `status`
- `created_at` (for sorting)
- `priority` (for query optimization)

### ai_worker.processing_jobs

Stores AI processing job details.

```json
{
  "_id": ObjectId,
  "request_id": ObjectId,  // Reference to api_service.requests
  "job_type": "inference",  // inference, training, batch_process
  "model_name": "bert-base",
  "status": "processing",  // queued, processing, completed, failed
  "celery_task_id": "abc-123-def-456",
  "result": {
    "predictions": [0.95, 0.02, 0.03],
    "confidence": 0.95,
    "processing_time_ms": 1200
  },
  "error": null,
  "resource_usage": {
    "cpu_percent": 85.5,
    "memory_mb": 2048,
    "gpu_percent": 90.0
  },
  "created_at": ISODate("2026-05-15T10:30:00Z"),
  "started_at": ISODate("2026-05-15T10:31:00Z"),
  "completed_at": ISODate("2026-05-15T10:33:00Z"),
  "retry_count": 0,
  "max_retries": 3
}
```

**Indexes:**
- `request_id`
- `celery_task_id` (unique)
- `status`
- `created_at`

### notification_service.notifications

Stores notification records.

```json
{
  "_id": ObjectId,
  "user_id": ObjectId,  // Reference to users
  "notification_type": "email",  // email, push, sms
  "channel": "processing_complete",
  "template_name": "job_completed",
  "status": "sent",  // pending, sent, failed, bounced
  "recipient": "user@example.com",
  "subject": "Your processing job has completed",
  "content": "...",
  "metadata": {
    "job_id": ObjectId,
    "priority": "high"
  },
  "error_message": null,
  "retry_count": 0,
  "created_at": ISODate("2026-05-15T10:30:00Z"),
  "sent_at": ISODate("2026-05-15T10:31:00Z"),
  "read_at": null
}
```

**Indexes:**
- `user_id`
- `status`
- `created_at`
- `sent_at`

### notification_service.notification_templates

Stores email and notification templates.

```json
{
  "_id": ObjectId,
  "name": "job_completed",
  "type": "email",
  "subject_template": "Your job has completed",
  "html_template": "<html>...</html>",
  "text_template": "Your job has completed",
  "variables": ["user_name", "job_id", "completion_time"],
  "active": true,
  "created_at": ISODate("2026-05-15T10:30:00Z"),
  "updated_at": ISODate("2026-05-15T10:30:00Z")
}
```

**Indexes:**
- `name` (unique)

### shared.events

Event log for audit trail and event replay.

```json
{
  "_id": ObjectId,
  "event_type": "user_created",
  "service": "auth_service",
  "aggregate_id": ObjectId,  // user_id, request_id, etc.
  "aggregate_type": "User",
  "version": 1,
  "timestamp": ISODate("2026-05-15T10:30:00Z"),
  "data": {
    "email": "user@example.com",
    "name": "John Doe"
  },
  "metadata": {
    "user_id": ObjectId,
    "ip_address": "192.168.1.1"
  }
}
```

**Indexes:**
- `aggregate_id`
- `event_type`
- `timestamp`
- Compound index: `(aggregate_id, version)`

## Relationships

```
users (1) ──── (M) refresh_tokens
        ├──── (M) requests
        └──── (M) notifications

requests (1) ──── (M) processing_jobs
```

## Data Retention

- **Users**: Retained indefinitely
- **Refresh Tokens**: Deleted after expiration (TTL index)
- **Requests**: 90 days (archive to cold storage after)
- **Notifications**: 30 days
- **Events**: 1 year

## Backup Strategy

- **Daily**: Incremental backup
- **Weekly**: Full backup
- **Monthly**: Archive to cold storage
- **Retention**: 6 months for backup, 1 year for archives

## Scaling Considerations

### Sharding Strategy

Consider sharding by `user_id` for collections with high volume:
- `requests`
- `notifications`
- `processing_jobs`

### Replication

- Production: 3-node replica set
- Staging: 2-node replica set
- Development: Single node

## Performance Optimization

### Index Strategy

1. **Query indexes**: Indexes on frequently queried fields
2. **Sort indexes**: Indexes on fields used in sorting
3. **Compound indexes**: For complex query patterns
4. **TTL indexes**: For automatic data cleanup

### Query Optimization Tips

```javascript
// Good: Uses index
db.requests.find({ status: "processing" })

// Good: Uses compound index
db.requests.find({ user_id: ObjectId, status: "processing" })

// Bad: Full collection scan (no index)
db.requests.find({ description: "text search" })
```

## Migration Procedures

### Adding a Field

```javascript
db.requests.updateMany(
  { new_field: { $exists: false } },
  { $set: { new_field: null } }
)
```

### Renaming a Field

```javascript
db.requests.updateMany(
  {},
  { $rename: { old_name: "new_name" } }
)
```

### Removing a Field

```javascript
db.requests.updateMany(
  {},
  { $unset: { field_to_remove: "" } }
)
```

## References

- [MongoDB Documentation](https://docs.mongodb.com/)
- [MongoDB Indexing Strategy](https://docs.mongodb.com/manual/core/data-model-design/)
- [MongoDB Best Practices](https://docs.mongodb.com/manual/core/schema-validation/)
