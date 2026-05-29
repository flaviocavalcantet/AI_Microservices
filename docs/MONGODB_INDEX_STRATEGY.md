# MongoDB Index Strategy Guide

## Overview

This document explains the indexing philosophy and patterns used across the AI platform's MongoDB repositories. Proper indexing is critical for query performance, especially at scale.

**Key Principle**: Every query pattern used in the application should have a corresponding index.

---

## Index Naming Convention

All indexes follow a consistent naming pattern for easy identification:

```
idx_<field1>[_<field2>]_<query_pattern>
```

Examples:
- `idx_user_created` — queries by user_id and sort by created_at
- `idx_status_created` — queries by status ordered by created_at
- `idx_provider_identity` — compound unique index on OAuth identity
- `idx_expires_ttl` — TTL index for auto-expiry

---

## Index Types & Usage

### 1. **Simple Indexes** (Single Field)

Used for basic equality filters and sorting.

```python
IndexModel(
    [("email", ASCENDING)],
    unique=True,
    name="idx_email",
    background=True,
)
```

**When to use:**
- High-cardinality fields (email, id, token_hash)
- Fields frequently used in WHERE clauses
- Unique constraints

**Current examples:**
- `users.email` — Auth service user lookups
- `refresh_tokens.token_hash` — Session token lookups

---

### 2. **Compound Indexes** (Multiple Fields)

Used for queries filtering on multiple fields and sorting.

**Rule of thumb**: Index field order matters for query performance:
1. **Equality fields first** (filters in WHERE clause)
2. **Range fields second** (inequality operators)
3. **Sort field last** (ORDER BY clause)

#### Example: User Jobs Query

```python
# Query: Find all jobs for a user, sorted by created_at descending
# Repository method:
# def find_by_user(self, user_id: str, limit=50, offset=0) -> Tuple[List[Job], int]:
#     self._find_paginated({"user_id": user_id}, limit, offset, "created_at", "desc")

IndexModel(
    [("user_id", ASCENDING), ("created_at", DESCENDING)],
    name="idx_user_created",
    background=True,
)
```

**Why this order?**
1. `user_id` ASCENDING (filter equality — narrows dataset first)
2. `created_at` DESCENDING (sort order — avoids in-memory sort)

#### Example: Status-based Queue Polling

```python
# Query: Find pending jobs, ordered by priority (priority-aware queue)
# Repository method: worker polling for PENDING jobs in priority order

IndexModel(
    [("priority", ASCENDING), ("created_at", ASCENDING)],
    name="idx_priority_queue",
    background=True,
    partialFilterExpression={"status": "pending"},  # Only index pending docs
)
```

**Why this structure?**
1. `priority` ASCENDING (queue processing order — lower numbers first)
2. `created_at` ASCENDING (FIFO within same priority)
3. **Partial filter** — Only index documents where status="pending" (saves space)

---

### 3. **Unique Indexes**

Enforce uniqueness on one or more fields. Prevent duplicate entries.

```python
# Unique email in users collection
IndexModel(
    [("email", ASCENDING)],
    unique=True,
    name="idx_email",
    background=True,
)
```

**Current examples:**
- `users.email` — One email per user
- `refresh_tokens.token_hash` — Each token appears once
- `ai_processing_results.input_hash` — Deduplication (see below)

---

### 4. **Sparse Unique Indexes**

Allow multiple `null` values while enforcing uniqueness on non-null documents.

```python
# Sparse unique on input_hash in ai_processing_results
# Purpose: Deduplicate identical inputs while allowing null hashes

IndexModel(
    [("input_hash", ASCENDING)],
    unique=True,
    sparse=True,           # ← Key: null values not indexed
    name="idx_input_hash_dedup",
    background=True,
)
```

**Why sparse?**
- Not all results have an input_hash (optional field)
- Without `sparse=True`, unique constraint fails on multiple nulls
- With `sparse=True`, multiple nulls allowed, but non-null values unique

**Current examples:**
- `ai_processing_results.input_hash` — Deduplication with optional hashes
- Optional profile fields in some services

---

### 5. **TTL Indexes** (Time-to-Live)

Automatically delete documents after a specified time.

```python
# Auto-delete expired refresh tokens
IndexModel(
    [("expires_at", ASCENDING)],
    expireAfterSeconds=0,      # ← Delete when expires_at <= now
    name="idx_expires_ttl",
    background=True,
)
```

**How it works:**
- MongoDB background process scans index every 60 seconds
- Deletes any document where `expires_at <= current_time`
- `expireAfterSeconds=0` means delete immediately when expired

**Current examples:**
- `refresh_tokens.expires_at` — Session token cleanup
- Could be used for: request logs, temporary caches, rate-limit counters

**Important notes:**
- TTL indexes cannot be used with compound indexes
- MongoDB checks every minute (not real-time)
- Perfect for maintenance-free data expiry

---

### 6. **Partial Indexes**

Index only a subset of documents matching a filter expression.

```python
# Only index pending jobs for efficient queue polling
IndexModel(
    [("priority", ASCENDING), ("created_at", ASCENDING)],
    name="idx_priority_queue",
    background=True,
    partialFilterExpression={"status": "pending"},  # ← Filter
)
```

**Benefits:**
- **Smaller index size** — Don't index completed/cancelled jobs
- **Faster lookups** — Index scans faster on smaller index
- **Targeted queries** — Perfect for queue polling patterns

**When to use:**
- Frequently queried subset of documents
- State-based filtering (active users, pending tasks, failed retries)

**Current examples:**
- `jobs.priority+created_at` with `status="pending"` filter
- Could be extended to: `users.is_active=true`, `results.status="success"`

---

## Index Performance Patterns

### ✅ Pattern 1: Equality + Sort

```python
# Query: db.jobs.find({"user_id": "123"}).sort("created_at", -1).limit(50)
# Index:
IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)])
```

**Why this works:**
1. Index narrows to user_id=123 (small subset)
2. Results already sorted by created_at (no in-memory sort)
3. MongoDB returns top 50 efficiently

---

### ✅ Pattern 2: Equality + Equality + Sort

```python
# Query: db.users.find({
#   "provider": "github",
#   "is_active": true
# }).sort("created_at", -1)
# Index:
IndexModel([
    ("provider", ASCENDING),
    ("is_active", ASCENDING),
    ("created_at", DESCENDING)
])
```

---

### ❌ Anti-Pattern: Wrong Field Order

```python
# WRONG: Sorting field before equality filter
IndexModel([("created_at", DESCENDING), ("user_id", ASCENDING)])
# ↑ MongoDB cannot use this for: find({"user_id": "123"}).sort("created_at", -1)

# WRONG: Descending on filter field (wastes space)
IndexModel([("user_id", DESCENDING), ("created_at", DESCENDING)])
# ↑ Direction doesn't matter for equality, only for sorting
```

---

## Query Analysis

Every repository method should be backed by an index. Here's how to verify:

### Step 1: Identify Query Pattern
```python
def find_by_user(self, user_id: str, limit=50, offset=0):
    return self._find_paginated(
        {"user_id": user_id},      # ← Filter: user_id
        limit, offset,
        "created_at",              # ← Sort field
        "desc"                      # ← Sort direction
    )
```

### Step 2: Determine Optimal Index
```python
# Filters: [user_id]
# Sort: created_at (descending)
# Index should be:
IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)])
```

### Step 3: Implement in Repository
```python
def ensure_indexes(self) -> None:
    indexes = [
        IndexModel(
            [("user_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_user_created",
            background=True,
        ),
    ]
    self._db[self.COLLECTION_NAME].create_indexes(indexes)
```

---

## Current Index Coverage

### auth_service.users
| Index | Filters | Sort | Purpose |
|-------|---------|------|---------|
| `idx_provider_identity` | provider, provider_user_id | — | OAuth identity lookup |
| `idx_email` | email | — | Email-based user lookup |
| `idx_active_created` | is_active | created_at | Active user listing |

**Queries covered:**
- ✅ Find user by provider+provider_user_id (OAuth login)
- ✅ Find user by email (fallback lookup)
- ✅ List active users paginated

---

### auth_service.refresh_tokens
| Index | Filters | Sort | Purpose |
|-------|---------|------|---------|
| `idx_token_hash` | token_hash | — | Token lookup (unique) |
| `idx_session_revoked` | session_id, revoked_at | — | Family revocation sweep |
| `idx_user_created` | user_id | created_at | User token history |
| `idx_expires_ttl` | expires_at | — | Auto-expiry (TTL) |

**Queries covered:**
- ✅ Refresh token validation (by hash)
- ✅ Revoke token family (session_id sweep)
- ✅ User session history
- ✅ Automatic expired token deletion

---

### api_service.jobs
| Index | Filters | Sort | Purpose |
|-------|---------|------|---------|
| `idx_user_created` | user_id | created_at desc | User job list |
| `idx_status_created` | status | created_at desc | Status queue polling |
| `idx_user_status` | user_id, status | — | Dashboard filtering |
| `idx_type_status` | job_type, status | — | Analytics queries |
| `idx_priority_queue` | priority (pending only) | created_at | Priority queue (partial) |

**Queries covered:**
- ✅ User jobs paginated by date
- ✅ Worker polling by status
- ✅ Dashboard status filtering
- ✅ Admin analytics
- ✅ Priority-based queue polling

---

### ai_worker.ai_processing_results
| Index | Filters | Sort | Purpose |
|-------|---------|------|---------|
| `idx_job_created` | job_id | created_at desc | Job result history |
| `idx_job_status` | job_id, status | — | Success lookup |
| `idx_user_created` | user_id | created_at desc | User result history |
| `idx_model_version_created` | model_name, model_version | created_at desc | Model analytics |
| `idx_input_hash_dedup` | input_hash (sparse unique) | — | Deduplication |

**Queries covered:**
- ✅ All attempts for a job (paginated)
- ✅ Latest successful result for job
- ✅ Per-user result history
- ✅ Model performance analytics
- ✅ Input deduplication (cache misses)

---

## Best Practices

### 1. **Always Use `background=True`**
```python
IndexModel([...], background=True)  # ✅ Correct
IndexModel([...])                    # ❌ May lock collection during creation
```

**Why:** Background index creation doesn't lock the collection, allowing reads/writes during index build.

---

### 2. **Name Your Indexes**
```python
IndexModel([...], name="idx_user_created")  # ✅ Descriptive
IndexModel([...])                           # ❌ Auto-generated names hard to track
```

**Why:** Named indexes are easier to monitor and drop if needed.

---

### 3. **Match Field Order to Query Pattern**

```python
# ✅ CORRECT: Index matches query pattern
# Query: find({"user_id": x}).sort("created_at", -1)
IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)])

# ❌ WRONG: Index doesn't match query pattern
# Query: find({"user_id": x}).sort("created_at", -1)
IndexModel([("created_at", DESCENDING), ("user_id", ASCENDING)])  # Wrong order!
```

---

### 4. **Use Partial Indexes for Subsets**

```python
# ✅ CORRECT: Only index pending jobs (most common query)
IndexModel(
    [("status", ASCENDING), ("created_at", DESCENDING)],
    partialFilterExpression={"status": "pending"}
)

# ❌ WRONG: Index all documents (wastes space)
IndexModel([("status", ASCENDING), ("created_at", DESCENDING)])
```

---

### 5. **TTL Indexes Stand Alone**

```python
# ✅ CORRECT: TTL index on one field
IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0)

# ❌ WRONG: TTL as part of compound index (doesn't work)
IndexModel([("user_id", ASCENDING), ("expires_at", ASCENDING)], expireAfterSeconds=0)
```

---

## Monitoring & Maintenance

### List All Indexes for a Collection
```python
from pymongo.database import Database

def list_indexes(db: Database, collection_name: str):
    col = db[collection_name]
    for index in col.list_indexes():
        print(f"{index['name']}: {index['key']}")
```

### Find Unused Indexes
```python
# MongoDB Enterprise/Atlas provides: db.collection.aggregate([
#   { $indexStats: {} }
# ])
# Check accesses.ops field for access count
```

### Drop an Index
```python
db[collection_name].drop_index("idx_name")
```

### Rebuild All Indexes
```python
db[collection_name].reindex()
```

---

## Performance Guidelines

| Scenario | Index Strategy |
|----------|-----------------|
| High-cardinality field (email, id) | Simple unique index |
| Filter + Sort | Compound index (filter fields first) |
| Multiple independent queries | Create separate indexes |
| Optional field | Sparse index |
| Auto-expire data | TTL index |
| Subset of documents | Partial index |
| Very large collection (millions of docs) | Analyze query patterns, create targeted indexes |

---

## Adding New Indexes

When adding a new query pattern:

1. **Identify the query method** in your repository
2. **Extract filters and sort** from the query
3. **Create compound index** with filters first, then sort field
4. **Implement `ensure_indexes()`** in repository
5. **Run `scripts/mongodb/ensure_indexes.py`** at deployment

Example:
```python
# New method in repository
def find_by_type_and_status(self, job_type: str, status: str):
    return self._collection.find({"job_type": job_type, "status": status})

# Add index
IndexModel(
    [("job_type", ASCENDING), ("status", ASCENDING)],
    name="idx_type_status",
    background=True,
)

# Deploy: python scripts/mongodb/ensure_indexes.py --service api_service
```

---

## References

- [MongoDB Index Types](https://docs.mongodb.com/manual/indexes/)
- [Compound Index Field Order](https://docs.mongodb.com/manual/tutorial/optimize-query-performance-with-indexes-and-projections/)
- [TTL Indexes](https://docs.mongodb.com/manual/core/index-ttl/)
- [Partial Indexes](https://docs.mongodb.com/manual/core/index-partial/)
- [Index Performance](https://docs.mongodb.com/manual/core/query-optimization/)
