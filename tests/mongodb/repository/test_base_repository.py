"""tests/mongodb/repository/test_base_repository.py

Layer 3 — MongoBaseRepository unit tests using a mocked collection.

Tests every shared CRUD method, the index-initialisation lifecycle, and
the metrics-forwarding behaviour — all without any real MongoDB I/O.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest
from pymongo.errors import DuplicateKeyError, PyMongoError

from shared.shared_infrastructure.src.mongodb.base_repository import (
    DuplicateEntityError,
    MongoBaseRepository,
    RepositoryError,
)


# ─────────────────────────────────────────────────────────────────────────────
# Minimal concrete subclass used throughout these tests
# ─────────────────────────────────────────────────────────────────────────────

class _Item:
    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name


class _ItemRepository(MongoBaseRepository[_Item]):
    COLLECTION_NAME = "items"
    _ensure_calls = 0

    def ensure_indexes(self) -> None:
        self._ensure_calls += 1

    def _to_document(self, entity: _Item) -> Dict[str, Any]:
        return {"_id": entity.id, "name": entity.name, "created_at": datetime.now(timezone.utc)}

    def _to_entity(self, document: Dict[str, Any]) -> _Item:
        return _Item(id=document["_id"], name=document["name"])


# ─────────────────────────────────────────────────────────────────────────────
# Fixture
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def repo(mock_db, mock_collection):
    """Return a concrete repo wired to mock_db.

    The collection property is patched so every operation reaches mock_collection.
    """
    r = _ItemRepository(mock_db)
    # Pre-mark indexes as ensured so collection access doesn't call ensure_indexes
    r._indexes_ensured = True
    # Patch _collection to always return our mock
    with patch.object(
        _ItemRepository, "_collection", new_callable=PropertyMock, return_value=mock_collection
    ):
        yield r


@pytest.fixture
def repo_with_metrics(mock_db, mock_collection):
    """Repo wired to a real MongoMetrics instance via a mock connection manager."""
    from shared.shared_infrastructure.src.mongodb.connection import MongoMetrics
    mgr = MagicMock()
    mgr.metrics = MongoMetrics()
    r = _ItemRepository(mock_db, connection_manager=mgr)
    r._indexes_ensured = True
    with patch.object(
        _ItemRepository, "_collection", new_callable=PropertyMock, return_value=mock_collection
    ):
        yield r, mgr.metrics


# ─────────────────────────────────────────────────────────────────────────────
# initialize / ensure_indexes lifecycle
# ─────────────────────────────────────────────────────────────────────────────

class TestInitialize:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_initialize_calls_ensure_indexes(self, mock_db):
        r = _ItemRepository(mock_db)
        r.initialize()
        assert r._ensure_calls == 1
        assert r._indexes_ensured is True

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_initialize_is_idempotent(self, mock_db):
        r = _ItemRepository(mock_db)
        r.initialize()
        r.initialize()
        r.initialize()
        assert r._ensure_calls == 1  # ensure_indexes called exactly once

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_initialize_logs_error_but_does_not_raise_on_pymongo_error(
        self, mock_db
    ):
        r = _ItemRepository(mock_db)
        r.ensure_indexes = MagicMock(
            side_effect=PyMongoError("index creation failed")
        )
        r.initialize()  # must NOT raise
        assert r._indexes_ensured is False  # marked failed, stays False

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_collection_access_triggers_lazy_initialize(
        self, mock_db, mock_collection
    ):
        r = _ItemRepository(mock_db)
        ensure_spy = MagicMock()
        r.ensure_indexes = ensure_spy
        # Access collection — should trigger lazy init
        _ = r._collection
        ensure_spy.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# save
# ─────────────────────────────────────────────────────────────────────────────

class TestSave:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_save_calls_replace_one_with_upsert(self, repo, mock_collection):
        item = _Item("id-1", "widget")
        repo.save(item)
        mock_collection.replace_one.assert_called_once()
        args, kwargs = mock_collection.replace_one.call_args
        assert args[0] == {"_id": "id-1"}
        assert kwargs.get("upsert") is True

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_save_stamps_updated_at(self, repo, mock_collection):
        item = _Item("id-2", "gadget")
        repo.save(item)
        _, kwargs = mock_collection.replace_one.call_args
        doc = mock_collection.replace_one.call_args[0][1]
        assert "updated_at" in doc

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_save_returns_entity(self, repo):
        item = _Item("id-3", "thing")
        result = repo.save(item)
        assert result is item

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_save_wraps_duplicate_key_error(self, repo, mock_collection):
        mock_collection.replace_one.side_effect = DuplicateKeyError("E11000")
        with pytest.raises(DuplicateEntityError):
            repo.save(_Item("dup", "x"))

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_save_wraps_generic_pymongo_error(self, repo, mock_collection):
        mock_collection.replace_one.side_effect = PyMongoError("write failed")
        with pytest.raises(RepositoryError):
            repo.save(_Item("err", "y"))


# ─────────────────────────────────────────────────────────────────────────────
# find_by_id
# ─────────────────────────────────────────────────────────────────────────────

class TestFindById:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_entity_when_document_found(self, repo, mock_collection):
        mock_collection.find_one.return_value = {"_id": "id-1", "name": "widget"}
        result = repo.find_by_id("id-1")
        assert isinstance(result, _Item)
        assert result.id == "id-1"
        assert result.name == "widget"

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_none_when_document_not_found(self, repo, mock_collection):
        mock_collection.find_one.return_value = None
        result = repo.find_by_id("missing")
        assert result is None

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_queries_by_underscore_id(self, repo, mock_collection):
        mock_collection.find_one.return_value = None
        repo.find_by_id("abc")
        mock_collection.find_one.assert_called_with({"_id": "abc"})

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_wraps_pymongo_error(self, repo, mock_collection):
        mock_collection.find_one.side_effect = PyMongoError("read failed")
        with pytest.raises(RepositoryError):
            repo.find_by_id("x")


# ─────────────────────────────────────────────────────────────────────────────
# delete
# ─────────────────────────────────────────────────────────────────────────────

class TestDelete:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_true_when_document_deleted(self, repo, mock_collection):
        mock_collection.delete_one.return_value = MagicMock(deleted_count=1)
        assert repo.delete("id-1") is True

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_false_when_document_not_found(self, repo, mock_collection):
        mock_collection.delete_one.return_value = MagicMock(deleted_count=0)
        assert repo.delete("ghost") is False

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_wraps_pymongo_error(self, repo, mock_collection):
        mock_collection.delete_one.side_effect = PyMongoError("delete failed")
        with pytest.raises(RepositoryError):
            repo.delete("x")


# ─────────────────────────────────────────────────────────────────────────────
# exists
# ─────────────────────────────────────────────────────────────────────────────

class TestExists:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_true_when_count_is_one(self, repo, mock_collection):
        mock_collection.count_documents.return_value = 1
        assert repo.exists("id-1") is True

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_false_when_count_is_zero(self, repo, mock_collection):
        mock_collection.count_documents.return_value = 0
        assert repo.exists("ghost") is False

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_uses_limit_one_for_efficiency(self, repo, mock_collection):
        mock_collection.count_documents.return_value = 0
        repo.exists("x")
        mock_collection.count_documents.assert_called_with({"_id": "x"}, limit=1)


# ─────────────────────────────────────────────────────────────────────────────
# _find_paginated
# ─────────────────────────────────────────────────────────────────────────────

class TestFindPaginated:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_entities_and_total(self, repo, mock_collection):
        mock_collection.count_documents.return_value = 2
        docs = [{"_id": "a", "name": "A"}, {"_id": "b", "name": "B"}]
        cursor = MagicMock()
        cursor.__iter__ = MagicMock(return_value=iter(docs))
        cursor.sort.return_value = cursor
        cursor.skip.return_value = cursor
        cursor.limit.return_value = cursor
        mock_collection.find.return_value = cursor

        entities, total = repo._find_paginated({}, limit=10, offset=0)
        assert total == 2
        assert len(entities) == 2

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_applies_sort_skip_limit_in_order(self, repo, mock_collection):
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.skip.return_value = cursor
        cursor.limit.return_value = cursor
        cursor.__iter__ = MagicMock(return_value=iter([]))
        mock_collection.find.return_value = cursor
        mock_collection.count_documents.return_value = 0

        repo._find_paginated({}, limit=5, offset=10, sort_field="created_at", sort_order="desc")
        cursor.sort.assert_called_once()
        cursor.skip.assert_called_with(10)
        cursor.limit.assert_called_with(5)

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_wraps_pymongo_error(self, repo, mock_collection):
        mock_collection.count_documents.side_effect = PyMongoError("fail")
        with pytest.raises(RepositoryError):
            repo._find_paginated({}, limit=10, offset=0)


# ─────────────────────────────────────────────────────────────────────────────
# _update_fields
# ─────────────────────────────────────────────────────────────────────────────

class TestUpdateFields:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_calls_find_one_and_update_with_set(self, repo, mock_collection):
        mock_collection.find_one_and_update.return_value = {
            "_id": "id-1", "name": "updated"
        }
        result = repo._update_fields("id-1", {"name": "updated"})
        assert result is not None
        call_args = mock_collection.find_one_and_update.call_args
        update_doc = call_args[0][1]
        assert "name" in update_doc["$set"]
        assert "updated_at" in update_doc["$set"]

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_none_when_document_not_found(self, repo, mock_collection):
        mock_collection.find_one_and_update.return_value = None
        result = repo._update_fields("ghost", {"name": "x"})
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Metrics forwarding
# ─────────────────────────────────────────────────────────────────────────────

class TestMetricsForwarding:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_save_increments_total_operations(self, repo_with_metrics, mock_collection):
        repo, metrics = repo_with_metrics
        mock_collection.replace_one.return_value = MagicMock()
        repo.save(_Item("m1", "x"))
        assert metrics.total_operations == 1

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_save_failure_increments_failed_operations(self, repo_with_metrics, mock_collection):
        repo, metrics = repo_with_metrics
        mock_collection.replace_one.side_effect = PyMongoError("write error")
        with pytest.raises(RepositoryError):
            repo.save(_Item("m2", "y"))
        assert metrics.failed_operations == 1

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_find_by_id_increments_ops(self, repo_with_metrics, mock_collection):
        repo, metrics = repo_with_metrics
        mock_collection.find_one.return_value = None
        repo.find_by_id("z")
        assert metrics.total_operations == 1

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_delete_increments_ops(self, repo_with_metrics, mock_collection):
        repo, metrics = repo_with_metrics
        mock_collection.delete_one.return_value = MagicMock(deleted_count=1)
        repo.delete("z")
        assert metrics.total_operations == 1

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_record_op_safe_when_no_connection_manager(self, mock_db, mock_collection):
        r = _ItemRepository(mock_db, connection_manager=None)
        r._indexes_ensured = True
        with patch.object(
            _ItemRepository, "_collection", new_callable=PropertyMock, return_value=mock_collection
        ):
            r.save(_Item("safe", "no-metrics"))  # must not raise
