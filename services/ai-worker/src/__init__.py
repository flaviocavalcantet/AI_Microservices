"""AI Worker: Asynchronous AI/ML Task Processing

Responsibility: Long-running AI inference/training tasks, batch processing

Architecture Layers:
- domain/: Business logic for ML tasks and processing
- application/: Use cases for task execution and result handling
- infrastructure/: Task queuing (Celery), ML framework integration
- presentation/: HTTP routes for task submission and status

Processing patterns:
- Celery worker processes long-running tasks asynchronously
- Tasks queued through RabbitMQ
- Results stored in MongoDB
- Health monitoring and error recovery
"""

__version__ = "1.0.0"
__author__ = "AI Platform Team"
