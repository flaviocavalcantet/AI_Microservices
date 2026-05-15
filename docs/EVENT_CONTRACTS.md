# Event-Driven Architecture: Event Contracts Strategy

## Overview

Events are the primary mechanism for inter-service communication in this platform. Events enable loose coupling, asynchronous processing, and audit trails. This guide defines how to design, version, and serialize events.

## Event Principles

1. **Framework-Independent**: Events are pure data structures (dataclasses, dicts)
2. **JSON Serializable**: All events must serialize/deserialize to/from JSON
3. **Immutable**: Events represent facts that occurred, not commands
4. **Domain Events**: Occur within a service (UserCreated, JobStarted)
5. **Integration Events**: Cross-service communication (ProcessingCompleted, NotificationSent)
6. **Versionable**: Events evolve over time with backward compatibility

## Event Architecture

```
Service A
├─ Domain Layer
│   └─ UserCreatedEvent (domain event)
├─ Application Layer
│   └─ Publish domain event
├─ Infrastructure Layer
│   └─ Serialize & publish to RabbitMQ
│
↓ (RabbitMQ Message Bus)
│
Service B
├─ Infrastructure Layer
│   └─ Receive & deserialize
├─ Event Handler
│   └─ Trigger use case
├─ Application Layer
│   └─ Handle event
└─ Domain Layer
    └─ Business logic executed
```

## Event Naming Conventions

### Domain Events (Within Service)

Occur within a bounded context. Represent past facts in past tense.

```
Format: {EntityName}{Action}Event

Examples:
- UserCreatedEvent
- UserActivatedEvent
- JobStartedEvent
- JobCompletedEvent
- PaymentProcessedEvent
- NotificationSentEvent
```

### Integration Events (Between Services)

Cross-service events. Also use past tense.

```
Format: {Domain}.{EntityName}.{Action}

Examples:
- user.User.Created
- job.Job.Completed
- notification.Notification.Sent
- auth.User.Authenticated
```

## Event Metadata Strategy

Every event includes standardized metadata for tracking and correlation.

### Standard Event Metadata

```python
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4
from typing import Dict, Any

@dataclass
class EventMetadata:
    """Standardized metadata for all events"""
    
    # Unique event identifier
    event_id: str = field(default_factory=lambda: str(uuid4()))
    
    # Correlation ID for tracing request across services
    correlation_id: str = field(default_factory=lambda: str(uuid4()))
    
    # Causation ID - what event caused this event
    causation_id: str = ""
    
    # When event occurred
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # Which service published
    source_service: str = ""
    
    # Version of event schema
    event_version: str = "1.0"
    
    # User who triggered (if applicable)
    user_id: str = ""
    
    # Request/transaction ID
    request_id: str = ""
    
    # Optional context/tags
    context: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DomainEvent:
    """Base class for all domain events"""
    
    # Event-specific data
    aggregate_id: str  # ID of entity that changed (user_id, job_id, etc.)
    aggregate_type: str  # Type of entity (User, Job, etc.)
    
    # Standard metadata
    metadata: EventMetadata
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to JSON-serializable dict"""
        return {
            "event_type": self.__class__.__name__,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "metadata": {
                "event_id": self.metadata.event_id,
                "correlation_id": self.metadata.correlation_id,
                "causation_id": self.metadata.causation_id,
                "timestamp": self.metadata.timestamp,
                "source_service": self.metadata.source_service,
                "event_version": self.metadata.event_version,
                "user_id": self.metadata.user_id,
                "request_id": self.metadata.request_id,
                "context": self.metadata.context,
            },
            "data": self._get_event_data()
        }
    
    def _get_event_data(self) -> Dict[str, Any]:
        """Override in subclasses to return event-specific data"""
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DomainEvent":
        """Deserialize event from dict"""
        metadata_data = data.get("metadata", {})
        metadata = EventMetadata(
            event_id=metadata_data.get("event_id", ""),
            correlation_id=metadata_data.get("correlation_id", ""),
            causation_id=metadata_data.get("causation_id", ""),
            timestamp=metadata_data.get("timestamp", ""),
            source_service=metadata_data.get("source_service", ""),
            event_version=metadata_data.get("event_version", "1.0"),
            user_id=metadata_data.get("user_id", ""),
            request_id=metadata_data.get("request_id", ""),
            context=metadata_data.get("context", {})
        )
        
        return cls(
            aggregate_id=data.get("aggregate_id", ""),
            aggregate_type=data.get("aggregate_type", ""),
            metadata=metadata,
            **data.get("data", {})
        )
```

## Event Versioning Strategy

Events evolve over time. Use semantic versioning with backward compatibility.

### Version Format
```
{Major}.{Minor}

Examples:
- 1.0 (initial version)
- 1.1 (added optional field)
- 2.0 (breaking change - required field added)
```

### Versioning Rules

1. **1.0 → 1.1 (Minor)**: Adding optional fields
   - Old event handlers can still process
   - New handlers can use additional data

2. **1.1 → 2.0 (Major)**: Adding required fields or removing optional ones
   - Breaking change - old handlers may fail
   - Requires explicit upgrade strategy

### Version Evolution Example

```python
# Version 1.0: Initial JobCreated event
@dataclass
class JobCreatedEvent(DomainEvent):
    job_id: str
    input_data: Dict[str, Any]
    
    def _get_event_data(self):
        return {
            "job_id": self.job_id,
            "input_data": self.input_data
        }

# Later: Version 1.1 - Added optional priority field (backward compatible)
@dataclass
class JobCreatedEvent(DomainEvent):
    job_id: str
    input_data: Dict[str, Any]
    priority: str = "medium"  # Optional field with default
    
    def _get_event_data(self):
        return {
            "job_id": self.job_id,
            "input_data": self.input_data,
            "priority": self.priority
        }

# Even later: Version 2.0 - Restructured (breaking change)
@dataclass
class JobCreatedEvent(DomainEvent):
    job_id: str
    parameters: Dict[str, Any]  # Renamed from input_data
    priority: str = "medium"
    estimated_duration_seconds: int = 0  # New required field
    
    def _get_event_data(self):
        return {
            "job_id": self.job_id,
            "parameters": self.parameters,
            "priority": self.priority,
            "estimated_duration_seconds": self.estimated_duration_seconds
        }
```

### Handling Version Mismatches

```python
class EventDeserializer:
    """Deserialize events handling multiple versions"""
    
    @staticmethod
    def deserialize(data: Dict[str, Any]) -> DomainEvent:
        event_type = data.get("event_type")
        version = data.get("metadata", {}).get("event_version", "1.0")
        
        # Route to appropriate deserializer
        if event_type == "JobCreatedEvent":
            if version.startswith("1"):
                return JobCreatedEventV1.from_dict(data)
            elif version.startswith("2"):
                return JobCreatedEventV2.from_dict(data)
            else:
                raise ValueError(f"Unknown event version: {version}")

class JobCreatedEventV1(DomainEvent):
    """Handle legacy v1.x events"""
    pass

class JobCreatedEventV2(DomainEvent):
    """Handle current v2.x events"""
    pass
```

## Example Events

### 1. UserAuthenticated

**Service**: auth-service  
**Trigger**: User successfully logs in  
**Purpose**: Notify other services of successful authentication

```python
@dataclass
class UserAuthenticatedEvent(DomainEvent):
    """Fired when user successfully authenticates"""
    
    # Event-specific data
    user_id: str
    email: str
    authentication_method: str  # "password", "oauth", "mfa"
    ip_address: str
    user_agent: str
    session_id: str
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "authentication_method": self.authentication_method,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "session_id": self.session_id,
        }

# Example event instance
auth_event = UserAuthenticatedEvent(
    aggregate_id="user_123",
    aggregate_type="User",
    metadata=EventMetadata(
        source_service="auth-service",
        user_id="user_123",
        request_id="req_456",
        correlation_id="corr_789"
    ),
    user_id="user_123",
    email="john@example.com",
    authentication_method="password",
    ip_address="192.168.1.1",
    user_agent="Mozilla/5.0...",
    session_id="sess_abc123"
)

# Serialized to JSON:
{
    "event_type": "UserAuthenticatedEvent",
    "aggregate_id": "user_123",
    "aggregate_type": "User",
    "metadata": {
        "event_id": "evt_xyz789",
        "correlation_id": "corr_789",
        "causation_id": "",
        "timestamp": "2026-05-15T10:30:00",
        "source_service": "auth-service",
        "event_version": "1.0",
        "user_id": "user_123",
        "request_id": "req_456",
        "context": {}
    },
    "data": {
        "user_id": "user_123",
        "email": "john@example.com",
        "authentication_method": "password",
        "ip_address": "192.168.1.1",
        "user_agent": "Mozilla/5.0...",
        "session_id": "sess_abc123"
    }
}
```

### 2. JobCreated

**Service**: api-service  
**Trigger**: User submits a processing job  
**Purpose**: Notify ai-worker to start processing and notification-service to track

```python
@dataclass
class JobCreatedEvent(DomainEvent):
    """Fired when a processing job is created"""
    
    # Event-specific data
    job_id: str
    user_id: str
    job_type: str  # "inference", "training", "batch_process"
    input_parameters: Dict[str, Any]
    priority: str  # "low", "medium", "high"
    timeout_seconds: int
    estimated_duration_seconds: int
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "user_id": self.user_id,
            "job_type": self.job_type,
            "input_parameters": self.input_parameters,
            "priority": self.priority,
            "timeout_seconds": self.timeout_seconds,
            "estimated_duration_seconds": self.estimated_duration_seconds,
        }

# Example event instance
job_event = JobCreatedEvent(
    aggregate_id="job_123",
    aggregate_type="Job",
    metadata=EventMetadata(
        source_service="api-service",
        user_id="user_123",
        request_id="req_456",
        correlation_id="corr_789"
    ),
    job_id="job_123",
    user_id="user_123",
    job_type="inference",
    input_parameters={
        "model": "bert-base",
        "text": "Analyze this sentiment..."
    },
    priority="high",
    timeout_seconds=300,
    estimated_duration_seconds=120
)

# Serialized to JSON:
{
    "event_type": "JobCreatedEvent",
    "aggregate_id": "job_123",
    "aggregate_type": "Job",
    "metadata": {
        "event_id": "evt_abc123",
        "correlation_id": "corr_789",
        "causation_id": "",
        "timestamp": "2026-05-15T10:35:00",
        "source_service": "api-service",
        "event_version": "1.0",
        "user_id": "user_123",
        "request_id": "req_456",
        "context": {}
    },
    "data": {
        "job_id": "job_123",
        "user_id": "user_123",
        "job_type": "inference",
        "input_parameters": {
            "model": "bert-base",
            "text": "Analyze this sentiment..."
        },
        "priority": "high",
        "timeout_seconds": 300,
        "estimated_duration_seconds": 120
    }
}
```

### 3. JobCompleted

**Service**: ai-worker  
**Trigger**: Processing job finishes successfully  
**Purpose**: Notify api-service and notification-service of completion

```python
@dataclass
class JobCompletedEvent(DomainEvent):
    """Fired when a processing job completes successfully"""
    
    # Event-specific data
    job_id: str
    user_id: str
    job_type: str
    status: str  # "success", "partial_success", "failed"
    result: Dict[str, Any]
    output_data: Dict[str, Any]
    processing_time_ms: int
    resource_usage: Dict[str, Any]  # cpu%, memory, gpu%
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "user_id": self.user_id,
            "job_type": self.job_type,
            "status": self.status,
            "result": self.result,
            "output_data": self.output_data,
            "processing_time_ms": self.processing_time_ms,
            "resource_usage": self.resource_usage,
        }

# Example event instance
completion_event = JobCompletedEvent(
    aggregate_id="job_123",
    aggregate_type="Job",
    metadata=EventMetadata(
        source_service="ai-worker",
        user_id="user_123",
        causation_id="evt_abc123",  # Caused by JobCreatedEvent
        correlation_id="corr_789",  # Same correlation as original request
        context={
            "worker_id": "worker_01",
            "gpu_device": "cuda:0"
        }
    ),
    job_id="job_123",
    user_id="user_123",
    job_type="inference",
    status="success",
    result={
        "predictions": [0.95, 0.03, 0.02],
        "confidence": 0.95,
        "model_version": "1.2.0"
    },
    output_data={
        "sentiment": "positive",
        "score": 0.95
    },
    processing_time_ms=1543,
    resource_usage={
        "cpu_percent": 78.5,
        "memory_mb": 2048,
        "gpu_percent": 92.3
    }
)

# Serialized to JSON:
{
    "event_type": "JobCompletedEvent",
    "aggregate_id": "job_123",
    "aggregate_type": "Job",
    "metadata": {
        "event_id": "evt_xyz456",
        "correlation_id": "corr_789",
        "causation_id": "evt_abc123",
        "timestamp": "2026-05-15T10:37:32.123",
        "source_service": "ai-worker",
        "event_version": "1.0",
        "user_id": "user_123",
        "request_id": "req_456",
        "context": {
            "worker_id": "worker_01",
            "gpu_device": "cuda:0"
        }
    },
    "data": {
        "job_id": "job_123",
        "user_id": "user_123",
        "job_type": "inference",
        "status": "success",
        "result": {
            "predictions": [0.95, 0.03, 0.02],
            "confidence": 0.95,
            "model_version": "1.2.0"
        },
        "output_data": {
            "sentiment": "positive",
            "score": 0.95
        },
        "processing_time_ms": 1543,
        "resource_usage": {
            "cpu_percent": 78.5,
            "memory_mb": 2048,
            "gpu_percent": 92.3
        }
    }
}
```

## Correlation ID Tracing

Correlation IDs enable request tracing across all services.

```
User Request → api-service (correlation_id: corr_789)
                   ↓
                Creates Job (JobCreatedEvent with corr_789)
                   ↓
                RabbitMQ publishes with corr_789
                   ↓
                ai-worker subscribes, receives corr_789
                   ↓
                Processes job, emits JobCompletedEvent with corr_789
                   ↓
                notification-service receives with corr_789
                   ↓
                Sends notification with corr_789 in logs

# Full trace in logs:
2026-05-15 10:35:00 [corr_789] api-service: Job created
2026-05-15 10:35:01 [corr_789] ai-worker: Processing started
2026-05-15 10:37:32 [corr_789] ai-worker: Processing completed
2026-05-15 10:37:33 [corr_789] notification-service: Email sent
```

## Event Publishing Implementation

```python
# infrastructure/messaging/event_publisher.py
class EventPublisher:
    """Publish domain events to message broker"""
    
    def __init__(self, rabbitmq_url: str, service_name: str):
        self.service_name = service_name
        self.connection = pika.BlockingConnection(
            pika.URLParameters(rabbitmq_url)
        )
        self.channel = self.connection.channel()
    
    def publish(self, event: DomainEvent, routing_key: str = None):
        """Publish event to message broker
        
        Args:
            event: Domain event to publish
            routing_key: Optional custom routing key
        """
        # Set source service and timestamp if not already set
        event.metadata.source_service = self.service_name
        if not event.metadata.timestamp:
            event.metadata.timestamp = datetime.utcnow().isoformat()
        
        # Default routing key from event type
        if not routing_key:
            routing_key = f"domain.{event.__class__.__name__}.{event.aggregate_type}"
        
        # Serialize to JSON
        message = json.dumps(event.to_dict(), default=str)
        
        # Publish with RabbitMQ
        self.channel.basic_publish(
            exchange="domain_events",
            routing_key=routing_key,
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2,  # Persistent
                content_type="application/json",
                headers={"correlation_id": event.metadata.correlation_id}
            )
        )

# Usage in application layer
class CreateJobUseCase:
    def __init__(self, repository, event_publisher):
        self.repository = repository
        self.event_publisher = event_publisher
    
    def execute(self, request, correlation_id: str, request_id: str):
        # Create job
        job = Job.create(request.parameters)
        
        # Save to repository
        job_id = self.repository.save(job)
        
        # Publish event
        event = JobCreatedEvent(
            aggregate_id=job_id,
            aggregate_type="Job",
            metadata=EventMetadata(
                correlation_id=correlation_id,
                request_id=request_id,
                user_id=request.user_id
            ),
            job_id=job_id,
            user_id=request.user_id,
            # ... other event data
        )
        
        self.event_publisher.publish(event)
        
        return job_id
```

## Event Subscription Implementation

```python
# infrastructure/messaging/event_handlers.py
class EventHandler:
    """Subscribe to and handle domain events"""
    
    def __init__(self, rabbitmq_url: str):
        self.connection = pika.BlockingConnection(
            pika.URLParameters(rabbitmq_url)
        )
        self.channel = self.connection.channel()
    
    def subscribe(self, event_type: str, callback, routing_key: str = None):
        """Subscribe to event type"""
        queue = self.channel.queue_declare(
            queue=f"{event_type}_queue",
            durable=True
        ).method.queue
        
        if not routing_key:
            routing_key = f"domain.{event_type}.*"
        
        self.channel.queue_bind(
            exchange="domain_events",
            queue=queue,
            routing_key=routing_key
        )
        
        def handle_message(ch, method, properties, body):
            try:
                # Deserialize event
                data = json.loads(body)
                event = EventDeserializer.deserialize(data)
                
                # Call handler
                callback(event)
                
                # Acknowledge
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                logger.error(f"Error handling event: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        
        self.channel.basic_consume(
            queue=queue,
            on_message_callback=handle_message
        )
        
        self.channel.start_consuming()

# Usage in notification service
from infrastructure.messaging.event_handlers import EventHandler

handler = EventHandler(rabbitmq_url)

def handle_job_completed(event: JobCompletedEvent):
    """Handle job completion - send notification"""
    use_case = SendNotificationUseCase(notification_repository)
    use_case.execute(
        user_id=event.user_id,
        message=f"Job {event.job_id} completed successfully",
        correlation_id=event.metadata.correlation_id
    )

handler.subscribe("JobCompletedEvent", handle_job_completed)
```

## Event Best Practices

1. **Use Past Tense**: Events represent things that happened
   - ✅ `UserCreatedEvent`
   - ❌ `CreateUserEvent`

2. **Include Identity**: Always include aggregate ID
   - ✅ `user_id`, `job_id`, `order_id`
   - ❌ Generic `id` field

3. **Immutable Data**: Event data should never change
   - ✅ Once published, event is final
   - ❌ Don't modify events in transit

4. **Correlation Tracking**: Propagate correlation IDs
   - ✅ Every event includes `correlation_id`
   - ❌ Breaking correlation chain

5. **Timestamps**: Always include ISO 8601 timestamps
   - ✅ `2026-05-15T10:35:00Z`
   - ❌ Unix timestamps or relative times

6. **Versioning**: Plan for schema evolution
   - ✅ Add optional fields with defaults
   - ❌ Required fields without migration

7. **Metadata Consistency**: Standard metadata across all events
   - ✅ `event_id`, `correlation_id`, `timestamp`
   - ❌ Event-specific metadata fields

## References

- [Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html)
- [Domain-Driven Design Events](https://vaughnvernon.com/the-idddd-sample-is-on-github/)
- [Distributed Tracing](https://opentelemetry.io/)
