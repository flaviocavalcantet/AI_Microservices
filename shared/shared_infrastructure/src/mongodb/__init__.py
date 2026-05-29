"""shared_infrastructure/mongodb public surface."""

from .base_repository import (
    DuplicateEntityError,
    MongoBaseRepository,
    RepositoryError,
)
from .config import MongoDBConfig
from .connection import MongoConnectionManager, MongoMetrics
from .object_id_wrapper import ObjectIdWrapper, unwrap_id, wrap_id

__all__ = [
    "MongoConnectionManager",
    "MongoMetrics",
    "MongoDBConfig",
    "MongoBaseRepository",
    "RepositoryError",
    "DuplicateEntityError",
    "ObjectIdWrapper",
    "wrap_id",
    "unwrap_id",
]
