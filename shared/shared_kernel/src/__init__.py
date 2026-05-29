"""shared_kernel public surface."""

from .entities import BaseEntity
from .repositories import IPageableRepository, IRepository

__all__ = [
    "BaseEntity",
    "IRepository",
    "IPageableRepository",
]
