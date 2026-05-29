"""tests/mongodb/unit/test_object_id_wrapper.py

Layer 1 — ObjectIdWrapper unit tests.

Covers all conversion paths, type checking, equality, and serialization.
No I/O; all tests run in milliseconds.
"""

import pytest
from bson import ObjectId
from bson.errors import InvalidId

from shared.shared_infrastructure.src.mongodb.object_id_wrapper import (
    ObjectIdWrapper,
    wrap_id,
    unwrap_id,
)


# ─────────────────────────────────────────────────────────────────────────────
# Construction
# ─────────────────────────────────────────────────────────────────────────────

class TestConstruction:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_from_string_stores_string(self):
        uid = "550e8400-e29b-41d4-a716-446655440000"
        w = ObjectIdWrapper.from_string(uid)
        assert w.as_string() == uid

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_from_object_id_stores_object_id(self):
        oid = ObjectId()
        w = ObjectIdWrapper.from_object_id(oid)
        assert w.as_object_id() == oid

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_from_string_empty_raises(self):
        with pytest.raises(ValueError):
            ObjectIdWrapper.from_string("")

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_from_string_non_string_raises(self):
        with pytest.raises((TypeError, ValueError)):
            ObjectIdWrapper.from_string(None)  # type: ignore

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_from_object_id_wrong_type_raises(self):
        with pytest.raises(TypeError):
            ObjectIdWrapper.from_object_id("not-an-objectid")  # type: ignore

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_init_with_invalid_type_raises(self):
        with pytest.raises(TypeError):
            ObjectIdWrapper(12345)  # type: ignore

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_from_any_accepts_string(self):
        uid = "abc-123"
        w = ObjectIdWrapper.from_any(uid)
        assert w.as_string() == uid

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_from_any_accepts_object_id(self):
        oid = ObjectId()
        w = ObjectIdWrapper.from_any(oid)
        assert w.as_object_id() == oid

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_from_any_accepts_wrapper(self):
        uid = "already-wrapped"
        w = ObjectIdWrapper.from_string(uid)
        w2 = ObjectIdWrapper.from_any(w)
        assert w2.as_string() == uid

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_from_any_accepts_extended_json(self):
        oid = ObjectId()
        extended = {"$oid": str(oid)}
        w = ObjectIdWrapper.from_any(extended)
        assert w.as_object_id() == oid

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_from_any_invalid_type_raises(self):
        with pytest.raises(TypeError):
            ObjectIdWrapper.from_any(42)


# ─────────────────────────────────────────────────────────────────────────────
# Type checking
# ─────────────────────────────────────────────────────────────────────────────

class TestTypeChecking:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_is_string_true_for_string_wrapper(self):
        w = ObjectIdWrapper.from_string("some-uuid")
        assert w.is_string() is True
        assert w.is_object_id() is False

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_is_object_id_true_for_objectid_wrapper(self):
        w = ObjectIdWrapper.from_object_id(ObjectId())
        assert w.is_object_id() is True
        assert w.is_string() is False

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_valid_objectid_hex_string_passes_is_valid(self):
        oid_hex = str(ObjectId())
        w = ObjectIdWrapper.from_string(oid_hex)
        assert w.is_valid_object_id() is True

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_uuid_string_fails_is_valid_object_id(self):
        w = ObjectIdWrapper.from_string("not-a-valid-oid-hex-string")
        assert w.is_valid_object_id() is False


# ─────────────────────────────────────────────────────────────────────────────
# Conversions
# ─────────────────────────────────────────────────────────────────────────────

class TestConversions:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_object_id_as_string_returns_hex(self):
        oid = ObjectId()
        w = ObjectIdWrapper.from_object_id(oid)
        assert w.as_string() == str(oid)

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_valid_hex_string_converts_to_object_id(self):
        oid = ObjectId()
        w = ObjectIdWrapper.from_string(str(oid))
        assert w.as_object_id() == oid

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_invalid_string_to_object_id_raises(self):
        w = ObjectIdWrapper.from_string("not-a-hex-objectid")
        with pytest.raises(ValueError):
            w.as_object_id()

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_as_hex_string_for_object_id(self):
        oid = ObjectId()
        w = ObjectIdWrapper.from_object_id(oid)
        assert w.as_hex_string() == str(oid)


# ─────────────────────────────────────────────────────────────────────────────
# Equality and hashing
# ─────────────────────────────────────────────────────────────────────────────

class TestEqualityAndHashing:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_two_wrappers_with_same_string_are_equal(self):
        uid = "same-id"
        assert ObjectIdWrapper.from_string(uid) == ObjectIdWrapper.from_string(uid)

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_wrapper_equals_raw_string(self):
        uid = "raw-string-id"
        w = ObjectIdWrapper.from_string(uid)
        assert w == uid

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_wrapper_equals_object_id(self):
        oid = ObjectId()
        w = ObjectIdWrapper.from_object_id(oid)
        assert w == oid

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_different_ids_not_equal(self):
        a = ObjectIdWrapper.from_string("id-a")
        b = ObjectIdWrapper.from_string("id-b")
        assert a != b

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_wrapper_usable_as_dict_key(self):
        w = ObjectIdWrapper.from_string("key-id")
        d = {w: "value"}
        assert d[w] == "value"

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_wrapper_usable_in_set(self):
        w1 = ObjectIdWrapper.from_string("same")
        w2 = ObjectIdWrapper.from_string("same")
        assert len({w1, w2}) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Serialization
# ─────────────────────────────────────────────────────────────────────────────

class TestSerialization:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_to_dict_for_object_id_uses_oid_key(self):
        oid = ObjectId()
        w = ObjectIdWrapper.from_object_id(oid)
        d = w.to_dict()
        assert "$oid" in d
        assert d["$oid"] == str(oid)

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_to_dict_for_string_uses_string_key(self):
        uid = "uuid-string"
        w = ObjectIdWrapper.from_string(uid)
        d = w.to_dict()
        assert "$string" in d
        assert d["$string"] == uid

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_to_json_value_returns_string(self):
        uid = "json-id"
        w = ObjectIdWrapper.from_string(uid)
        assert w.to_json_value() == uid

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_str_repr_for_string_wrapper(self):
        w = ObjectIdWrapper.from_string("my-id")
        assert "my-id" in str(w)

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_repr_includes_id_value(self):
        uid = "repr-id"
        w = ObjectIdWrapper.from_string(uid)
        assert uid in repr(w)


# ─────────────────────────────────────────────────────────────────────────────
# Convenience functions
# ─────────────────────────────────────────────────────────────────────────────

class TestConvenienceFunctions:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_wrap_id_string(self):
        uid = "wrap-string"
        w = wrap_id(uid)
        assert isinstance(w, ObjectIdWrapper)
        assert w.as_string() == uid

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_wrap_id_object_id(self):
        oid = ObjectId()
        w = wrap_id(oid)
        assert w.as_object_id() == oid

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_unwrap_id_from_wrapper(self):
        uid = "unwrap-test"
        w = ObjectIdWrapper.from_string(uid)
        assert unwrap_id(w) == uid

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_unwrap_id_from_string(self):
        assert unwrap_id("plain-string") == "plain-string"

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_unwrap_id_from_object_id(self):
        oid = ObjectId()
        assert unwrap_id(oid) == str(oid)
