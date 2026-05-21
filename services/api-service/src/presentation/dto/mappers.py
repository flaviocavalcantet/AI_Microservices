# Mapper utilities for converting between DTOs and domain entities

from typing import Type, TypeVar, Generic, List
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)
E = TypeVar('E')  # Entity type


class BaseMapper(Generic[T, E]):
    """Base mapper for converting between DTOs and entities
    
    Override map_to_dto() and map_to_entity() in subclasses
    """
    
    @staticmethod
    def map_to_dto(entity: E) -> T:
        """Convert domain entity to DTO
        
        Override in subclass
        """
        raise NotImplementedError("Subclass must implement map_to_dto")
    
    @staticmethod
    def map_to_entity(dto: T) -> E:
        """Convert DTO to domain entity
        
        Override in subclass
        """
        raise NotImplementedError("Subclass must implement map_to_entity")
    
    @staticmethod
    def map_list_to_dtos(entities: List[E]) -> List[T]:
        """Convert list of entities to DTOs"""
        return [BaseMapper.map_to_dto(e) for e in entities]
    
    @staticmethod
    def map_list_to_entities(dtos: List[T]) -> List[E]:
        """Convert list of DTOs to entities"""
        return [BaseMapper.map_to_entity(d) for d in dtos]


class ResponseMapper:
    """Helper for building consistent response objects"""
    
    @staticmethod
    def success(data=None, correlation_id=None, pagination=None):
        """Build success response"""
        from services.api_service.src.presentation.dto import DataResponse, ListResponse
        
        if isinstance(data, list):
            return {
                "status": "success",
                "data": data,
                "pagination": pagination or {},
                "correlation_id": correlation_id,
            }
        else:
            return {
                "status": "success",
                "data": data,
                "correlation_id": correlation_id,
            }
    
    @staticmethod
    def error(code, message, details=None, correlation_id=None):
        """Build error response"""
        return {
            "status": "error",
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
            "correlation_id": correlation_id,
        }
