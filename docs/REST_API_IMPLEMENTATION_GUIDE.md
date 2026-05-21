# REST API Implementation Guide

## Quick Start - Adding New Endpoints

This guide shows how to add new API endpoints using the established patterns.

### Step 1: Define Request/Response Schemas

Create `services/api_service/src/presentation/routes/v1/{resource}/schemas.py`:

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any

class CreateItemRequest(BaseModel):
    """Request to create item"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    
    @validator("name")
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v

class UpdateItemRequest(BaseModel):
    """Request to update item"""
    name: Optional[str] = None
    description: Optional[str] = None

class ListItemsQuery(BaseModel):
    """Query parameters for listing items"""
    limit: int = Field(default=50, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default="created_at")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
```

### Step 2: Define Response Models

Create `services/api_service/src/presentation/routes/v1/{resource}/responses.py`:

```python
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class ItemResponse(BaseModel):
    """Item data for API responses"""
    id: str
    name: str
    description: Optional[str]
    created_at: str

class CreateItemResponse(BaseModel):
    """Response for successful item creation"""
    status: str = "success"
    data: ItemResponse
    correlation_id: Optional[str]
    timestamp: str
```

### Step 3: Create Controller (Routes)

Create `services/api_service/src/presentation/routes/v1/{resource}/controller.py`:

```python
from flask import request, jsonify
from datetime import datetime
from services.api_service.src.presentation.routes.v1.base import BaseBlueprint
from services.api_service.src.presentation.middleware.validation import validate_request_schema
from services.api_service.src.presentation.routes.v1.items.schemas import (
    CreateItemRequest,
    UpdateItemRequest,
    ListItemsQuery
)
from services.api_service.src.errors import NotFoundError

class ItemsBlueprint(BaseBlueprint):
    """Items API blueprint
    
    Endpoints:
    - POST /api/v1/items - Create
    - GET /api/v1/items - List
    - GET /api/v1/items/{id} - Get
    - PUT /api/v1/items/{id} - Update
    - DELETE /api/v1/items/{id} - Delete
    """
    
    def __init__(self):
        super().__init__("items", "/api/v1/items")
        self.setup_routes()
    
    def setup_routes(self):
        
        @self.bp.route("", methods=["POST"])
        @validate_request_schema(CreateItemRequest)
        def create_item():
            """Create new item"""
            self.log_request("POST", "create_item")
            
            try:
                schema = request.validated_data
                
                # Get use case from container
                use_case = self.resolve("create_item_use_case")
                item = use_case.execute(schema)
                
                response = {
                    "status": "success",
                    "data": item.to_dict(),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
                
                self.log_response(201, "create_item", item_id=item.id)
                return jsonify(response), 201
            
            except Exception as e:
                self.log_error(e, "create_item")
                raise
        
        @self.bp.route("", methods=["GET"])
        def list_items():
            """List items"""
            self.log_request("GET", "list_items")
            
            try:
                # Get use case
                use_case = self.resolve("list_items_use_case")
                items, total = use_case.execute(request.args)
                
                response = {
                    "status": "success",
                    "data": [i.to_dict() for i in items],
                    "pagination": {
                        "limit": request.args.get("limit", 50),
                        "offset": request.args.get("offset", 0),
                        "total": total,
                    },
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
                
                self.log_response(200, "list_items")
                return jsonify(response), 200
            
            except Exception as e:
                self.log_error(e, "list_items")
                raise
        
        @self.bp.route("/<item_id>", methods=["GET"])
        def get_item(item_id):
            """Get item by ID"""
            self.log_request("GET", "get_item", item_id=item_id)
            
            try:
                use_case = self.resolve("get_item_use_case")
                item = use_case.execute(item_id)
                
                if not item:
                    raise NotFoundError("Item")
                
                response = {
                    "status": "success",
                    "data": item.to_dict(),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
                
                self.log_response(200, "get_item", item_id=item_id)
                return jsonify(response), 200
            
            except NotFoundError:
                raise
            except Exception as e:
                self.log_error(e, "get_item", item_id=item_id)
                raise

# Export blueprint instance
items_bp = ItemsBlueprint()
```

### Step 4: Create Use Cases

Create `services/api_service/src/application/use_cases/item/create_item.py`:

```python
from services.api_service.src.logger import get_logger
from services.api_service.src.application.dto import CreateItemDTO
from services.api_service.src.domain.entities import Item

logger = get_logger(__name__)

class CreateItemUseCase:
    """Create new item use case"""
    
    def __init__(self, repository, event_publisher=None):
        self.repository = repository
        self.event_publisher = event_publisher
    
    def execute(self, input_dto: CreateItemDTO) -> Item:
        """Execute use case
        
        Args:
            input_dto: Create item DTO
        
        Returns:
            Created item entity
        """
        
        # 1. Create domain entity
        item = Item.create(
            name=input_dto.name,
            description=input_dto.description,
        )
        
        # 2. Validate business rules (done in entity)
        if item.is_invalid():
            raise ValueError("Invalid item")
        
        # 3. Save to repository
        saved_item = self.repository.save(item)
        
        # 4. Publish event
        if self.event_publisher:
            self.event_publisher.publish("ItemCreated", {
                "item_id": saved_item.id,
                "name": saved_item.name,
            })
        
        logger.info(f"Item created: {saved_item.id}")
        
        return saved_item
```

### Step 5: Create Domain Entity

Create `services/api_service/src/domain/entities/item.py`:

```python
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Item:
    """Item domain entity"""
    
    id: str
    name: str
    description: Optional[str]
    created_at: datetime
    
    @classmethod
    def create(cls, name: str, description: Optional[str] = None):
        """Factory method to create new item"""
        return cls(
            id=generate_id(),
            name=name,
            description=description,
            created_at=datetime.utcnow(),
        )
    
    def is_invalid(self) -> bool:
        """Check if item violates business rules"""
        return not self.name or len(self.name) > 100
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() + "Z",
        }
```

### Step 6: Create Repository Interface

Create `services/api_service/src/domain/repositories/item_repository.py`:

```python
from abc import ABC, abstractmethod
from typing import List, Optional

class IItemRepository(ABC):
    """Item repository interface"""
    
    @abstractmethod
    def save(self, item) -> object:
        """Save item"""
        pass
    
    @abstractmethod
    def find_by_id(self, item_id: str) -> Optional[object]:
        """Find item by ID"""
        pass
    
    @abstractmethod
    def find_all(self, limit=50, offset=0) -> tuple:
        """Find all items with pagination"""
        pass
    
    @abstractmethod
    def delete(self, item_id: str) -> bool:
        """Delete item"""
        pass
```

### Step 7: Register Blueprint

Update `services/api_service/src/presentation/app.py`:

```python
def _register_blueprints(app: Flask) -> None:
    """Register all blueprints"""
    
    app.register_blueprint(health_bp)
    jobs_bp.register(app)
    
    # Add new blueprint
    from services.api_service.src.presentation.routes.v1.items.controller import items_bp
    items_bp.register(app)
```

### Step 8: Register Use Cases in Container

Update `services/api_service/src/presentation/app.py` or container initialization:

```python
# Register use cases
container.register(
    "create_item_use_case",
    lambda: CreateItemUseCase(
        repository=container.resolve("item_repository"),
        event_publisher=container.resolve("event_publisher"),
    ),
    singleton=True
)

container.register(
    "list_items_use_case",
    lambda: ListItemsUseCase(
        repository=container.resolve("item_repository"),
    ),
    singleton=True
)

container.register(
    "get_item_use_case",
    lambda: GetItemUseCase(
        repository=container.resolve("item_repository"),
    ),
    singleton=True
)
```

## Directory Structure

```
presentation/
├── routes/
│   └── v1/
│       ├── base.py                  ← Base blueprint class
│       ├── health.py                ← Health endpoints
│       ├── jobs/
│       │   ├── __init__.py
│       │   ├── controller.py        ← Route handlers
│       │   ├── schemas.py           ← Request schemas
│       │   └── responses.py         ← Response models
│       ├── items/                   ← NEW RESOURCE
│       │   ├── __init__.py
│       │   ├── controller.py        ← Route handlers
│       │   ├── schemas.py           ← Request schemas
│       │   └── responses.py         ← Response models
│       └── v2/                      ← Future API versions
├── middleware/
│   ├── __init__.py
│   ├── validation.py               ← Request validation
│   ├── error_handler.py            ← Error handling
│   ├── correlation.py              ← Correlation IDs
│   └── auth.py                     ← (Future) Authentication
└── dto/
    ├── base.py                     ← Base response classes
    ├── common.py                   ← Common DTOs
    ├── mappers.py                  ← Entity ↔ DTO mappers
    └── __init__.py

application/
├── use_cases/
│   ├── item/                       ← NEW RESOURCE
│   │   ├── __init__.py
│   │   ├── create_item.py
│   │   ├── list_items.py
│   │   ├── get_item.py
│   │   ├── update_item.py
│   │   └── delete_item.py
│   ├── job/
│   │   └── ...
│   └── ...
├── dto/
│   ├── __init__.py
│   ├── item_dto.py                ← NEW RESOURCE
│   └── job_dto.py
└── exceptions.py

domain/
├── entities/
│   ├── __init__.py
│   ├── item.py                    ← NEW RESOURCE
│   ├── job.py
│   └── ...
├── repositories/
│   ├── __init__.py
│   ├── item_repository.py         ← NEW RESOURCE (interface only)
│   ├── job_repository.py
│   └── ...
└── value_objects/
    ├── __init__.py
    ├── item_status.py
    └── ...

infrastructure/
├── persistence/
│   └── mongodb/
│       ├── item_repository.py     ← NEW RESOURCE (implementation)
│       └── ...
└── ...
```

## Common Patterns

### Request/Response Validation

```python
@app.route("/items", methods=["POST"])
@validate_request_schema(CreateItemRequest)
def create_item():
    # request.validated_data contains validated Pydantic model
    schema = request.validated_data
    print(schema.name)  # Access fields
```

### Error Handling

```python
from services.api_service.src.errors import (
    ValidationError,
    NotFoundError,
    ConflictError
)

@app.route("/items", methods=["POST"])
def create_item():
    if not request.json.get("name"):
        raise ValidationError("Name is required")
    
    if item_exists(name):
        raise ConflictError(f"Item {name} already exists")
    
    return {"status": "success"}

# All errors automatically converted to:
# {
#   "status": "error",
#   "error": {
#     "code": "VALIDATION_ERROR",
#     "message": "Name is required"
#   }
# }
```

### Dependency Injection

```python
def my_route():
    container = get_container()
    
    # Resolve service
    use_case = container.resolve("my_use_case")
    
    # Use it
    result = use_case.execute(data)
    
    return result
```

### Logging with Context

```python
from services.api_service.src.logger import get_logger

logger = get_logger(__name__)

def my_route():
    logger.info("Starting operation")
    
    try:
        # Logs automatically include correlation_id from Flask context
        result = do_something()
        
        logger.info("Operation completed", extra={
            "item_id": result.id,
            "duration_ms": elapsed_time
        })
        
        return result
    
    except Exception as e:
        logger.error(f"Operation failed: {e}", exc_info=True)
        raise
```

### Pagination

```python
class ListItemsQuery(BaseModel):
    limit: int = Field(default=50, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default="created_at")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")

@app.route("/items", methods=["GET"])
def list_items():
    params = ListItemsQuery(**request.args.to_dict())
    
    items, total = use_case.execute(params)
    
    return {
        "data": items,
        "pagination": {
            "limit": params.limit,
            "offset": params.offset,
            "total": total,
            "pages": (total + params.limit - 1) // params.limit,
        }
    }
```

## Testing

### Test Controllers

```python
def test_create_item(client, mocker):
    """Test create item endpoint"""
    
    # Mock use case
    mock_use_case = mocker.Mock()
    mock_use_case.execute.return_value = Item(id="123", name="Test")
    
    # Register in container
    container = get_container()
    container.register_instance("create_item_use_case", mock_use_case)
    
    # Test request
    response = client.post(
        "/api/v1/items",
        json={"name": "Test Item"}
    )
    
    assert response.status_code == 201
    assert response.json["status"] == "success"
    mock_use_case.execute.assert_called_once()
```

### Test Use Cases

```python
def test_create_item_use_case():
    """Test create item use case"""
    
    # Mock repository
    mock_repo = Mock()
    mock_repo.save.return_value = Item(id="123", name="Test")
    
    # Create use case
    use_case = CreateItemUseCase(mock_repo)
    
    # Execute
    item = use_case.execute(CreateItemDTO(name="Test"))
    
    # Assert
    assert item.id == "123"
    assert item.name == "Test"
    mock_repo.save.assert_called_once()
```

### Test Schemas

```python
def test_create_item_schema():
    """Test request schema validation"""
    
    # Valid
    schema = CreateItemRequest(name="Valid Name")
    assert schema.name == "Valid Name"
    
    # Invalid - empty name
    with pytest.raises(ValidationError):
        CreateItemRequest(name="")
    
    # Invalid - missing required field
    with pytest.raises(ValidationError):
        CreateItemRequest()
```

## Naming Conventions

| Component | Pattern | Example |
|-----------|---------|---------|
| Blueprint | `{Resource}Blueprint` | `ItemsBlueprint` |
| Use Case | `{Action}{Resource}UseCase` | `CreateItemUseCase` |
| Entity | `{Resource}` | `Item` |
| Repository Impl | `Mongo{Resource}Repository` | `MongoItemRepository` |
| Request Schema | `{Action}{Resource}Request` | `CreateItemRequest` |
| Response Schema | `{Resource}Response` | `ItemResponse` |
| DTO | `{Resource}DTO` | `ItemDTO` |
| Error | `{Resource}NotFoundError` | `ItemNotFoundError` |

## API Versioning

### Adding V2

1. Create `presentation/routes/v2/` directory
2. Copy v1 routes as base
3. Modify as needed for breaking changes
4. Register v2 blueprints in factory
5. Keep v1 for backward compatibility

```python
# presentation/routes/v2/items/controller.py
class ItemsBlueprint(BaseBlueprint):
    def __init__(self):
        # Note: /api/v2/items instead of /api/v1/items
        super().__init__("items_v2", "/api/v2/items")
        self.setup_routes()
```

## Performance Considerations

### Caching

```python
from flask_caching import Cache

cache = Cache(config={'CACHE_TYPE': 'redis'})

@app.route("/items/<item_id>")
@cache.cached(timeout=300)  # 5 minutes
def get_item(item_id):
    return use_case.execute(item_id)
```

### Async (Future)

```python
# When implementing with Quart:
@app.route("/items", methods=["POST"])
async def create_item():
    item = await use_case.execute(request.json)
    return item
```

### Pagination Defaults

- Default limit: 50 items
- Max limit: 1000 items
- Default sort: created_at descending
- Always include total count

## Security Checklist

- [ ] Validate all inputs with Pydantic schemas
- [ ] Use strong type hints
- [ ] Never expose internal errors to clients
- [ ] Log errors securely (no PII)
- [ ] Use correlation IDs for tracing
- [ ] Sanitize database queries
- [ ] Rate limit endpoints
- [ ] Authenticate/authorize requests
- [ ] Use HTTPS in production
- [ ] Keep dependencies updated

## Troubleshooting

### Blueprint Not Registered

**Error**: `KeyError: 'items_bp'`

**Solution**: Ensure blueprint is imported and registered in `_register_blueprints()`

### Validation Not Working

**Error**: `ValidationError` not raised

**Solution**: Use `@validate_request_schema(MySchema)` decorator

### Container Resolution Fails

**Error**: `ValueError: Service not registered: my_service`

**Solution**: Ensure service registered in container before resolution

### Middleware Not Applying

**Error**: Request headers not in `g`

**Solution**: Check middleware is registered with `@app.before_request`

## Related Documentation

- [REST API Design](REST_API_DESIGN.md)
- [Clean Architecture](CLEAN_ARCHITECTURE.md)
- [Flask Application Template](FLASK_APPLICATION_TEMPLATE.md)
- [Error Handling](errors.py)
- [Configuration Management](CONFIGURATION.md)
