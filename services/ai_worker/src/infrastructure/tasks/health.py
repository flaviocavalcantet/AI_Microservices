"""Operational Celery tasks.

These tasks verify worker plumbing only; they do not run AI workloads.
"""

from ..messaging.celery_app import celery


@celery.task(name="ai_worker.health.ping")
def ping() -> dict:
    """Simple task for future worker liveness checks."""
    return {"status": "ok", "service": "ai_worker"}
