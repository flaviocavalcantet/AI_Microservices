# Routes package for v1 API

from .base import BaseBlueprint
from .health import health_bp
from .jobs.controller import jobs_bp
# Additional blueprints will be imported here as implemented

__all__ = [
    'BaseBlueprint',
    'health_bp',
    'jobs_bp',
]
