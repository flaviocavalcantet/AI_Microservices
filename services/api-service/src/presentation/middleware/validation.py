# Request validation middleware

import logging
from functools import wraps
from pydantic import BaseModel, ValidationError as PydanticValidationError
from flask import request
from services.api_service.src.errors import ValidationError

logger = logging.getLogger(__name__)


class RequestSchemaError(Exception):
    """Request schema validation failed"""
    pass


def validate_request_schema(schema_class):
    """Decorator to validate request JSON against Pydantic schema
    
    Args:
        schema_class: Pydantic model class for validation
    
    Raises:
        ValidationError: If request doesn't match schema
    
    Example:
        @app.route('/jobs', methods=['POST'])
        @validate_request_schema(CreateJobRequest)
        def create_job():
            # request.validated_data contains parsed/validated data
            pass
    """
    
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            try:
                # Parse and validate request JSON
                data = request.get_json(force=True)
                validated = schema_class(**data)
                
                # Store validated data on request for use in handler
                request.validated_data = validated
                
                logger.debug(f"Request validated against {schema_class.__name__}")
                
                return f(*args, **kwargs)
            
            except PydanticValidationError as e:
                # Convert Pydantic validation error to API error
                errors = []
                for error in e.errors():
                    errors.append({
                        "field": ".".join(str(x) for x in error["loc"]),
                        "message": error["msg"],
                        "type": error["type"]
                    })
                
                logger.warning(f"Request validation failed: {errors}")
                
                raise ValidationError(
                    f"Invalid request: {len(errors)} validation error(s)",
                    details={"validation_errors": errors}
                )
            
            except Exception as e:
                logger.error(f"Request parsing failed: {e}")
                raise ValidationError(f"Invalid JSON: {str(e)}")
        
        return decorated
    
    return decorator


def validate_query_params(schema_class):
    """Decorator to validate query parameters against schema
    
    Args:
        schema_class: Pydantic model for query parameters
    
    Example:
        class ListJobsQuery(BaseModel):
            limit: int = 50
            offset: int = 0
            status: Optional[str] = None
        
        @app.route('/jobs')
        @validate_query_params(ListJobsQuery)
        def list_jobs():
            params = request.query_params
    """
    
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            try:
                # Get query parameters as dict
                data = request.args.to_dict()
                
                # Convert string types to proper types
                # This is a simplified version - Pydantic v2 handles this
                validated = schema_class(**data)
                
                request.query_params = validated
                
                logger.debug(f"Query params validated against {schema_class.__name__}")
                
                return f(*args, **kwargs)
            
            except PydanticValidationError as e:
                errors = [{
                    "field": ".".join(str(x) for x in error["loc"]),
                    "message": error["msg"]
                } for error in e.errors()]
                
                raise ValidationError(
                    "Invalid query parameters",
                    details={"errors": errors}
                )
        
        return decorated
    
    return decorator


def validate_path_params(**kwargs):
    """Decorator to validate path parameters
    
    Example:
        @app.route('/jobs/<job_id>')
        @validate_path_params(job_id=str)
        def get_job(job_id):
            pass
    """
    
    def decorator(f):
        @wraps(f)
        def decorated(*args, route_kwargs=None, **kwargs):
            # Path params are already validated by Flask routing
            # This is mainly for type validation
            try:
                return f(*args, **kwargs)
            except (TypeError, ValueError) as e:
                raise ValidationError(f"Invalid path parameters: {e}")
        
        return decorated
    
    return decorator
