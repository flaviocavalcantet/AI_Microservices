"""V1 API Routes"""

from services.api_service.src.presentation.routes.v1.ai.controller import ai_bp
from services.api_service.src.presentation.routes.v1.jobs.controller import jobs_bp

__all__ = ["ai_bp", "jobs_bp"]
