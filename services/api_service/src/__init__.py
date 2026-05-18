"""API Service: Main API Gateway and Orchestration

Responsibility: RESTful API endpoints, request orchestration, cross-service coordination

Architecture Layers:
- domain/: Pure business logic (framework-independent)
- application/: Use cases and business rule orchestration
- infrastructure/: Database, messaging, external services
- presentation/: HTTP routes, middleware, controllers

The service follows Clean Architecture principles to maintain:
- Framework independence
- Testability without external dependencies
- Clear separation of concerns
- Loose coupling between services
"""

__version__ = "1.0.0"
__author__ = "AI Platform Team"
