"""Request validation helpers for Flask route handlers."""

from functools import wraps
import logging
from typing import Type

from flask import jsonify, request
from pydantic import BaseModel, ValidationError
from werkzeug.exceptions import BadRequest

logger = logging.getLogger(__name__)


def _validation_response(message: str, errors: list[dict], code: int = 400):
    """Build the API's standard validation error response."""
    return jsonify({
        "status": "error",
        "code": code,
        "error": message,
        "details": {"validation_errors": errors},
    }), code


def _format_pydantic_errors(error: ValidationError) -> list[dict]:
    """Convert Pydantic errors into a stable API shape."""
    return [
        {
            "field": ".".join(str(part) for part in item["loc"]),
            "message": item["msg"],
            "type": item["type"],
        }
        for item in error.errors()
    ]


def validate_json_body(schema_class: Type[BaseModel]):
    """Validate a JSON request body against a Pydantic schema.

    The validated model is attached to ``request.validated_data``.
    """
    def decorator(route_handler):
        @wraps(route_handler)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                return _validation_response(
                    "Content-Type must be application/json",
                    [{
                        "field": "body",
                        "message": "Request body must be JSON",
                        "type": "type_error.json",
                    }],
                )

            try:
                data = request.get_json()
            except BadRequest:
                return _validation_response(
                    "Invalid JSON body",
                    [{
                        "field": "body",
                        "message": "Malformed JSON",
                        "type": "value_error.jsondecode",
                    }],
                )

            if data is None:
                data = {}

            try:
                request.validated_data = schema_class(**data)
            except ValidationError as error:
                errors = _format_pydantic_errors(error)
                logger.warning("JSON body validation failed: %s", errors)
                return _validation_response("Invalid request body", errors)

            return route_handler(*args, **kwargs)

        return wrapper

    return decorator


def validate_query_params(schema_class: Type[BaseModel]):
    """Validate query parameters against a Pydantic schema.

    The validated model is attached to ``request.validated_query``.
    """
    def decorator(route_handler):
        @wraps(route_handler)
        def wrapper(*args, **kwargs):
            try:
                request.validated_query = schema_class(**request.args.to_dict())
            except ValidationError as error:
                errors = _format_pydantic_errors(error)
                logger.warning("Query parameter validation failed: %s", errors)
                return _validation_response("Invalid query parameters", errors)

            return route_handler(*args, **kwargs)

        return wrapper

    return decorator


def validate_path_params(schema_class: Type[BaseModel]):
    """Validate Flask path parameters against a Pydantic schema."""
    def decorator(route_handler):
        @wraps(route_handler)
        def wrapper(*args, **kwargs):
            try:
                schema_class(**kwargs)
            except ValidationError as error:
                errors = _format_pydantic_errors(error)
                logger.warning("Path parameter validation failed: %s", errors)
                return _validation_response("Invalid path parameters", errors)

            return route_handler(*args, **kwargs)

        return wrapper

    return decorator
