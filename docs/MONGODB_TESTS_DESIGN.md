# MongoDB Testing Design

## 1. Overview

This document defines the complete testing strategy for the MongoDB integration layer across the AI Microservices platform. It covers architecture decisions, fixture strategy, tooling, and the exact file layout to be implemented.

The strategy respects Clean Architecture boundaries: tests at each layer are isolated from the concerns of other layers. MongoDB concerns are tested only at the infrastructure layer, never at the domain or application layers.

---

## 2. Testing Philosophy

| Principle | Application |
|---|---|
| **Isolation** | Each layer tested independently; no MongoDB in domain tests |
| **Speed pyramid** | Unit (fast, many) → Mock-integration (medium) → Real-DB integration (slow, few) |
| **Determinism** | Every test produces the same result on every run |
| **No shared state** | Each test starts with a clean slate via fixtures |
| **Fail fast** | Tests reveal real breakage, not test-setup noise |
| **Clean Architecture** | Domain tests have zero infrastructure imports |

---

## 3. Test Layers

```
┌─────────────────────────────────────────────────────────┐
│  Layer 5 · Endpoint Tests                               │
│  Flask test client · real app factory · mocked MongoDB  │
├─────────────────────────────────────────────────────────┤
│  Layer 4 · Integration Tests (real MongoDB)             │
│  mongomock or live MongoDB · concrete repositories      │
├─────────────────────────────────────────────────────────┤
│  Layer 3 · Repository Unit Tests (mocked MongoDB)       │
│  unittest.mock · patch pymongo Collection methods       │
├─────────────────────────────────────────────────────────┤
│  Layer 2 · Infrastructure Unit Tests                    │
│  MongoConnectionManager · MongoMetrics · config         │
├─────────────────────────────────────────────────────────┤
│  Layer 1 · Shared Infrastructure Validation Tests       │
│  MongoDBConfig pydantic validation · ObjectIdWrapper    │
└─────────────────────────────────────────────────────────┘
```

---

## 4. File Layout

```
tests/
├── conftest.py                            ← root: sys.path, global marks
│
├── unit/
│   ├── auth_service/
│   │   ├── conftest.py                    ← existing Flask app fixtures
│   │   ├── test_auth_api_endpoints.py     ← existing (untouched)
│   │   ├── test_jwt_token_service.py      ← existing (untouched)
│   │   └── test_jwt_and_auth_flows.py     ← existing (untouched)
│   │
│   └── shared/
│       └── test_structured_logging.py    ← existing (untouched)
│
├── mongodb/                               ← NEW: all MongoDB-specific tests
│   │
│   ├── conftest.py                        ← shared MongoDB fixtures
│   │
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_mongo_config.py           ← Layer 1: pydantic config validation
│   │   ├── test_object_id_wrapper.py      ← Layer 1: ObjectIdWrapper unit tests
│   │   ├── test_connection_manager.py     ← Layer 2: MongoConnectionManager (mocked)
│   │   └── test_mongo_metrics.py          ← Layer 2: MongoMetrics counters & thread safety
│   │
│   ├── repository/
│   │   ├── __init__.py
│   │   ├── test_base_repository.py        ← Layer 3: MongoBaseRepository (mocked collection)
│   │   ├── test_user_repository.py        ← Layer 3: MongoUserRepository (mocked DB)
│   │   └── test_refresh_token_repository.py ← Layer 3: MongoRefreshTokenRepository (mocked)
│   │
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── conftest.py                    ← mongomock DB fixture
│   │   ├── test_user_repo_integration.py  ← Layer 4: real CRUD against mongomock
│   │   ├── test_refresh_token_repo_integration.py ← Layer 4: TTL & session revocation
│   │   └── test_mongo_wiring.py           ← Layer 4: wire_mongo() + index creation
│   │
│   └── endpoint/
│       ├── __init__.py
│       ├── conftest.py                    ← Flask app with mocked mongo_manager
│       ├── test_health_endpoints.py       ← Layer 5: /health/ready with MongoDB status
│       └── test_metrics_endpoints.py      ← Layer 5: /api/v1/auth/metrics/mongodb
```

---

## 5. Tooling

| Tool | Role | Install |
|---|---|---|
| `pytest` | Test runner | already in requirements-dev.txt |
| `pytest-mock` | `mocker` fixture (wraps `unittest.mock`) | `pip install pytest-mock` |
| `mongomock` | In-memory MongoDB for integration tests | `pip install mongomock` |
| `freezegun` | Freeze `datetime.utcnow()` in TTL / expiry tests | `pip install freezegun` |
| `pytest-cov` | Coverage reporting | already in requirements-dev.txt |

Add to `requirements-dev.txt`:
```
pytest-mock>=3.12.0
mongomock>=4.1.2
freezegun>=1.4.0
```

---

## 6. Fixture Strategy

### 6.1 `tests/mongodb/conftest.py` — Shared MongoDB Fixtures

| Fixture | Scope | Purpose |
|---|---|---|
| `mock_mongo_client` | function | `MagicMock` mimicking `MongoClient` |
| `mock_db` | function | `MagicMock` mimicking `Database` |
| `mock_collection` | function | `MagicMock` mimicking `Collection` with default cursor |
| `sample_user` | function | Valid `User` domain entity |
| `sample_refresh_token` | function | Valid `RefreshToken` domain entity |
| `sample_user_doc` | function | Raw MongoDB document matching `sample_user` |
| `sample_token_doc` | function | Raw MongoDB document matching `sample_refresh_token` |

### 6.2 `tests/mongodb/integration/conftest.py` — Integration Fixtures

| Fixture | Scope | Purpose |
|---|---|---|
| `mongomock_client` | session | `mongomock.MongoClient()` — one per session for speed |
| `integration_db` | function | Fresh database per test (dropped after each test) |
| `user_repo` | function | `MongoUserRepository(integration_db)` with indexes initialized |
| `token_repo` | function | `MongoRefreshTokenRepository(integration_db)` with indexes |

### 6.3 `tests/mongodb/endpoint/conftest.py` — Endpoint Fixtures

| Fixture | Scope | Purpose |
|---|---|---|
| `mock_manager` | function | `MagicMock` for `MongoConnectionManager` returning healthy status |
| `app_with_mongo` | function | Flask app with `mongo_manager` injected into container |
| `client_with_mongo` | function | Test client for `app_with_mongo` |

---

## 7. Mocking Strategy

### 7.1 Collection-Level Mock (repository unit tests)

```python
# Patch the collection accessor on the repository
mock_col = MagicMock()
with patch.object(repo, '_collection', new_callable=PropertyMock, return_value=mock_col):
    ...
```

This avoids patching pymongo internals and tests the repository's own logic cleanly.

### 7.2 MongoConnectionManager Mock (endpoint tests)

```python
manager = MagicMock(spec=MongoConnectionManager)
manager.health_status.return_value = {
    "mongodb": {"status": "healthy", "connected": True, "latency_ms": 1.2, ...}
}
container.register_instance("mongo_manager", manager)
```

### 7.3 mongomock (integration tests)

```python
import mongomock

@pytest.fixture
def integration_db():
    client = mongomock.MongoClient()
    db = client["auth_service_test"]
    yield db
    client.drop_database("auth_service_test")
```

`mongomock` implements the full pymongo API in memory, so all indexes, queries, upserts, and TTL queries work without a live MongoDB server.

---

## 8. Test Categories & Markers

```ini
# pyproject.toml markers (already registered):
unit        → Layer 1 & 2 & 3: no I/O, millisecond speed
integration → Layer 4: mongomock, no network
e2e         → Layer 5: Flask test client, full app stack
```

New marker added to `pyproject.toml`:
```ini
mongodb     → any test touching MongoDB code (union of layers 1-5)
```

---

## 9. Coverage Targets

| Module | Target |
|---|---|
| `shared_infrastructure/mongodb/connection.py` | ≥ 90% |
| `shared_infrastructure/mongodb/config.py` | ≥ 95% |
| `shared_infrastructure/mongodb/base_repository.py` | ≥ 95% |
| `shared_infrastructure/mongodb/object_id_wrapper.py` | ≥ 90% |
| `auth_service/infrastructure/repositories/mongo_user_repository.py` | ≥ 90% |
| `auth_service/infrastructure/repositories/mongo_refresh_token_repository.py` | ≥ 90% |
| `auth_service/infrastructure/repositories/mongo_wiring.py` | ≥ 85% |
| `auth_service/presentation/routes/health.py` | ≥ 85% |
| `auth_service/presentation/routes/v1/metrics.py` | ≥ 85% |

---

## 10. Key Test Scenarios

### Layer 1 — Config Validation
- Valid URI accepted; invalid URI raises `ValidationError`
- Environment values `development / staging / production` validated; unknown rejected
- Pool sizes per environment resolve to correct defaults
- `to_dict_safe()` never exposes credentials

### Layer 2 — Connection Manager
- `connect()` succeeds on first ping; stores client
- `connect()` retries on `ConnectionFailure`; raises after max retries exhausted
- `reconnect()` disconnects then reconnects
- `health_status()` returns structured dict with latency_ms and pool info
- `ping()` returns False when client is None; does not raise

### Layer 2 — Metrics
- `record_connect_attempt(success=True)` increments successes
- `record_op(latency_ms, success)` increments totals and accumulates latency
- `avg_latency_ms` returns correct average; None when no ops recorded
- Thread-safety: concurrent `record_op` calls do not corrupt counters

### Layer 3 — BaseRepository
- `save()` calls `replace_one` with upsert; stamps `updated_at`
- `save()` wraps `DuplicateKeyError` → `DuplicateEntityError`
- `save()` wraps generic `PyMongoError` → `RepositoryError`
- `find_by_id()` returns entity when doc found; None when absent
- `delete()` returns True when deleted_count > 0; False otherwise
- `initialize()` calls `ensure_indexes()` exactly once; idempotent on repeat calls
- `_record_op()` forwards to `connection_manager.metrics.record_op()`

### Layer 3 — UserRepository
- `find_by_provider()` queries with correct filter dict
- `find_by_email()` applies case-insensitive collation
- `_to_document()` maps all User fields; excludes `updated_at`
- `_to_entity()` reconstructs User with defaults for optional fields
- `ensure_indexes()` creates 3 named indexes on the users collection

### Layer 3 — RefreshTokenRepository
- `find_by_hash()` queries by `token_hash`
- `find_by_session_id()` returns list of tokens
- `revoke_session()` calls `update_many` with correct filter; returns modified count
- `delete_expired()` calls `delete_many` with `expires_at <= now`
- TTL index declared on `expires_at` with `expireAfterSeconds=0`

### Layer 4 — Integration (mongomock)
- Full save → find_by_id round-trip preserves all fields
- Unique index prevents duplicate provider identity
- Email lookup is case-insensitive
- Session revocation marks all active tokens in family
- `delete_expired()` removes only expired tokens
- `wire_mongo()` registers both repos and calls `initialize()` on each

### Layer 5 — Endpoints
- `GET /health/ready` returns 200 with `dependencies.database.status = "healthy"` when MongoDB healthy
- `GET /health/ready` returns 503 when MongoDB unhealthy
- `GET /health/ready` returns 200 with `"not_configured"` when no mongo_manager registered
- `GET /api/v1/auth/metrics/mongodb` returns 200 with full metrics dict
- `GET /api/v1/auth/metrics/mongodb` returns 503 when status is unhealthy

---

## 11. Running the Tests

```bash
# All MongoDB tests
pytest tests/mongodb/ -v

# Unit only (fast, no I/O)
pytest tests/mongodb/unit/ -v

# Repository mocked tests
pytest tests/mongodb/repository/ -v

# Integration (mongomock)
pytest tests/mongodb/integration/ -v

# Endpoint tests
pytest tests/mongodb/endpoint/ -v

# By marker
pytest -m mongodb -v

# With coverage
pytest tests/mongodb/ --cov=shared/shared_infrastructure/src/mongodb \
  --cov=services/auth_service/src/infrastructure/repositories \
  --cov=services/auth_service/src/presentation/routes \
  --cov-report=term-missing
```

---

## 12. `requirements-dev.txt` Additions

```
pytest-mock>=3.12.0
mongomock>=4.1.2
freezegun>=1.4.0
```
