# API service - main package initializer

__version__ = "1.0.0"
__author__ = "AI Platform Team"

from services.api_service.src.presentation.app import create_app

__all__ = ["create_app"]
