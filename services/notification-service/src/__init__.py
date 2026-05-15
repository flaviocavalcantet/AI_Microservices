"""Notification Service: Asynchronous Notification Delivery

Responsibility: Email, push, and SMS notifications with templating

Architecture Layers:
- domain/: Business logic for notification management
- application/: Use cases for sending notifications
- infrastructure/: Email service, notification templates, delivery tracking
- presentation/: HTTP routes for notification status

Processing patterns:
- Event-driven: Consumes domain events from other services
- Asynchronous delivery via Celery workers
- Retry logic with exponential backoff
- Notification templating and personalization
"""

__version__ = "1.0.0"
__author__ = "AI Platform Team"
