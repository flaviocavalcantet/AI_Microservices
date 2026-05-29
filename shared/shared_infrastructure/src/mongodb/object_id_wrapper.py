"""shared_infrastructure/mongodb/object_id_wrapper.py

ObjectId abstraction layer for future-proofing MongoDB migrations.

Currently, all domain entities use string UUIDs as _id. This module provides
a compatibility layer for scenarios where:
  - Converting to native MongoDB ObjectIds
  - Working with mixed string/ObjectId datasets
  - Migrating between ID schemes

The wrapper is optional; current implementation uses strings exclusively.
Domain layer should never import this directly.
"""

from __future__ import annotations

import logging
from typing import Any, Union

from bson import ObjectId
from bson.errors import InvalidId

logger = logging.getLogger(__name__)


class ObjectIdWrapper:
    """Wrapper for handling both string UUIDs and MongoDB ObjectIds.

    Design:
      - Stores internal representation (can be str or ObjectId)
      - Provides conversion utilities without modifying domain layer
      - Used only in infrastructure layer during serialization
      - Enables gradual migration if native ObjectIds become needed

    Example:
        # From a string UUID
        wrapped = ObjectIdWrapper.from_string("550e8400-e29b-41d4-a716-446655440000")

        # From ObjectId
        wrapped = ObjectIdWrapper.from_object_id(ObjectId())

        # Get as string (current default)
        string_id = wrapped.as_string()

        # Get as ObjectId (for raw queries)
        obj_id = wrapped.as_object_id()

        # Check type
        is_valid_oid = wrapped.is_valid_object_id()
    """

    def __init__(self, value: Union[str, ObjectId]) -> None:
        """Initialize with string or ObjectId."""
        if isinstance(value, str):
            self._value = value
            self._is_object_id = False
        elif isinstance(value, ObjectId):
            self._value = value
            self._is_object_id = True
        else:
            raise TypeError(f"Expected str or ObjectId, got {type(value).__name__}")

    # ── Factory methods ──────────────────────────────────────────────────────

    @classmethod
    def from_string(cls, string_id: str) -> ObjectIdWrapper:
        """Create wrapper from string UUID."""
        if not string_id or not isinstance(string_id, str):
            raise ValueError("string_id must be a non-empty string")
        return cls(string_id)

    @classmethod
    def from_object_id(cls, object_id: ObjectId) -> ObjectIdWrapper:
        """Create wrapper from MongoDB ObjectId."""
        if not isinstance(object_id, ObjectId):
            raise TypeError(f"Expected ObjectId, got {type(object_id).__name__}")
        return cls(object_id)

    @classmethod
    def from_any(cls, value: Any) -> ObjectIdWrapper:
        """Try to parse from any type."""
        if isinstance(value, ObjectIdWrapper):
            return value
        if isinstance(value, (str, ObjectId)):
            return cls(value)
        if isinstance(value, dict) and "$oid" in value:
            # Handle MongoDB extended JSON format {"$oid": "..."}
            try:
                return cls(ObjectId(value["$oid"]))
            except (InvalidId, TypeError) as exc:
                raise ValueError(f"Invalid ObjectId format: {exc}") from exc
        raise TypeError(
            f"Cannot parse ObjectIdWrapper from {type(value).__name__}: {value}"
        )

    # ── Conversions ──────────────────────────────────────────────────────────

    def as_string(self) -> str:
        """Return as string UUID."""
        if self._is_object_id:
            return str(self._value)
        return self._value

    def as_object_id(self) -> ObjectId:
        """Return as MongoDB ObjectId.

        If wrapper contains a string, attempts conversion.
        String must be a valid ObjectId hex string (24 hex chars).
        """
        if self._is_object_id:
            return self._value
        try:
            return ObjectId(self._value)
        except (InvalidId, TypeError) as exc:
            raise ValueError(
                f"Cannot convert string '{self._value}' to ObjectId: {exc}"
            ) from exc

    def as_hex_string(self) -> str:
        """Return ObjectId's hex representation.

        Only valid for ObjectIds; for strings, returns the string itself.
        """
        if self._is_object_id:
            return str(self._value)
        return self._value

    # ── Type checking ─────────────────────────────────────────────────────────

    def is_object_id(self) -> bool:
        """Return True if wrapped value is a native ObjectId."""
        return self._is_object_id

    def is_string(self) -> bool:
        """Return True if wrapped value is a string UUID."""
        return not self._is_object_id

    def is_valid_object_id(self) -> bool:
        """Return True if value can be converted to ObjectId."""
        if self._is_object_id:
            return True
        try:
            ObjectId(self._value)
            return True
        except (InvalidId, TypeError):
            return False

    # ── Comparison ───────────────────────────────────────────────────────────

    def __eq__(self, other: Any) -> bool:
        """Compare with another ObjectIdWrapper or primitive."""
        if isinstance(other, ObjectIdWrapper):
            return self.as_string() == other.as_string()
        if isinstance(other, str):
            return self.as_string() == other
        if isinstance(other, ObjectId):
            try:
                return self.as_object_id() == other
            except ValueError:
                return False
        return False

    def __hash__(self) -> int:
        """Allow use in sets and dicts."""
        return hash(self.as_string())

    # ── Serialization ────────────────────────────────────────────────────────

    def __str__(self) -> str:
        """String representation (for logging)."""
        if self._is_object_id:
            return f"ObjectId({str(self._value)})"
        return f"StringId({self._value})"

    def __repr__(self) -> str:
        """Developer representation."""
        return f"ObjectIdWrapper({self.as_string()!r})"

    def to_dict(self) -> dict:
        """Serialize to MongoDB extended JSON format."""
        if self._is_object_id:
            return {"$oid": str(self._value)}
        return {"$string": self._value}

    def to_json_value(self) -> str:
        """Return JSON-serializable string representation."""
        return self.as_string()


def wrap_id(value: Union[str, ObjectId]) -> ObjectIdWrapper:
    """Convenience function to wrap any ID value."""
    return ObjectIdWrapper.from_any(value)


def unwrap_id(wrapped: Union[ObjectIdWrapper, str, ObjectId]) -> str:
    """Convenience function to extract string representation."""
    if isinstance(wrapped, ObjectIdWrapper):
        return wrapped.as_string()
    if isinstance(wrapped, ObjectId):
        return str(wrapped)
    return wrapped
