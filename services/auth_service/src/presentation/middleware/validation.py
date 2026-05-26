"""Request validation middleware for auth-service routes."""

from functools import wraps
import logging
from typing import Type

from flask import request
from pydantic import BaseModel, ValidationError
from werkzeug.exceptions import BadRequest

from ..responses import error_response

logger = logging.getLogger(__name__)


def _format_pydantic_errors(error: ValidationError) -> list[dict]:
    return [
        {
            "field": ".".join(str(part) for part in item["loc"]),
            "message": item["msg"],
            "type": item["type"],
        }
        for item in error.errors()
    ]


def validate_json_body(schema_class: Type[BaseModel]):
    """Validate JSON body; attach result to ``request.validated_data``."""

    def decorator(route_handler):
        @wraps(route_handler)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                return error_response(
                    "Content-Type must be application/json",
                    error_code="VALIDATION_ERROR",
                    http_code=400,
                    details={"validation_errors": [{
                        "field": "body",
                        "message": "Request body must be JSON",
                        "type": "type_error.json",
                    }]},
                )

            try:
                data = request.get_json()
            except BadRequest:
                return error_response(
                    "Invalid JSON body",
                    error_code="VALIDATION_ERROR",
                    http_code=400,
                    details={"validation_errors": [{
                        "field": "body",
                        "message": "Malformed JSON",
                        "type": "value_error.jsondecode",
                    }]},
                )

            if data is None:
                data = {}

            try:
                request.validated_data = schema_class(**data)
            except ValidationError as exc:
                errors = _format_pydantic_errors(exc)
                logger.warning("JSON body validation failed", extra={"errors": errors})
                return error_response(
                    "Invalid request body",
                    error_code="VALIDATION_ERROR",
                    http_code=400,
                    details={"validation_errors": errors},
                )

            return route_handler(*args, **kwargs)

        return wrapper

    return decorator


def validate_query_params(schema_class: Type[BaseModel]):
    """Validate query string; attach result to ``request.validated_query``."""

    def decorator(route_handler):
        @wraps(route_handler)
        def wrapper(*args, **kwargs):
            try:
                request.validated_query = schema_class(**request.args.to_dict())
            except ValidationError as exc:
                errors = _format_pydantic_errors(exc)
                logger.warning("Query validation failed", extra={"errors": errors})
                return error_response(
                    "Invalid query parameters",
                    error_code="VALIDATION_ERROR",
                    http_code=400,
                    details={"validation_errors": errors},
                )
            return route_handler(*args, **kwargs)

        return wrapper

    return decorator
