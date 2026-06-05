"""tests/mongodb/repository/test_refresh_token_repository.py

Layer 3 — MongoRefreshTokenRepository unit tests (mocked collection).

Covers all repository methods: find_by_hash, find_by_session_id,
revoke_session, delete_expired, document mapping, and index declarations.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest
from pymongo.errors import PyMongoError

from services.auth_service.src.domain.entities.refresh_token import RefreshToken
from services.auth_service.src.infrastructure.repositories.mongo_refresh_token_repository import (
    MongoRefreshTokenRepository,
)
from shared.shared_infrastructure.src.mongodb.base_repository import RepositoryError


# ─────────────────────────────────────────────────────────────────────────────
# Fixture
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def repo(mock_db, mock_collection):
    r = MongoRefreshTokenRepository(mock_db)
    r._indexes_ensured = True
    with patch.object(
        MongoRefreshTokenRepository,
        "_collection",
        new_callable=PropertyMock,
        return_value=mock_collection,
    ):
        yield r


# ─────────────────────────────────────────────────────────────────────────────
# Index declaration
# ─────────────────────────────────────────────────────────────────────────────

class TestEnsureIndexes:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_calls_create_indexes(self, mock_db, mock_collection):
        r = MongoRefreshTokenRepository(mock_db)
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        r.ensure_indexes()
        mock_collection.create_indexes.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_four_indexes_declared(self, mock_db, mock_collection):
        r = MongoRefreshTokenRepository(mock_db)
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        r.ensure_indexes()
        indexes = mock_collection.create_indexes.call_args[0][0]
        assert len(indexes) == 4

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_token_hash_index_is_unique(self, mock_db, mock_collection):
        r = MongoRefreshTokenRepository(mock_db)
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        r.ensure_indexes()
        indexes = mock_collection.create_indexes.call_args[0][0]
        by_name = {idx.document["name"]: idx.document for idx in indexes}
        assert by_name["idx_token_hash"]["unique"] is True

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_ttl_index_has_expire_after_seconds_zero(self, mock_db, mock_collection):
        r = MongoRefreshTokenRepository(mock_db)
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        r.ensure_indexes()
        indexes = mock_collection.create_indexes.call_args[0][0]
        by_name = {idx.document["name"]: idx.document for idx in indexes}
        assert by_name["idx_expires_ttl"]["expireAfterSeconds"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# find_by_hash
# ─────────────────────────────────────────────────────────────────────────────

class TestFindByHash:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_none_when_not_found(self, repo, mock_collection):
        mock_collection.find_one.return_value = None
        assert repo.find_by_hash("nonexistent-hash") is None

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_queries_by_token_hash_field(self, repo, mock_collection):
        mock_collection.find_one.return_value = None
        repo.find_by_hash("abc123")
        mock_collection.find_one.assert_called_with({"token_hash": "abc123"})

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_refresh_token_entity(self, repo, mock_collection, sample_token_doc):
        mock_collection.find_one.return_value = sample_token_doc
        token = repo.find_by_hash(sample_token_doc["token_hash"])
        assert isinstance(token, RefreshToken)
        assert token.token_hash == sample_token_doc["token_hash"]

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_wraps_pymongo_error(self, repo, mock_collection):
        mock_collection.find_one.side_effect = PyMongoError("fail")
        with pytest.raises(RepositoryError):
            repo.find_by_hash("x")


# ─────────────────────────────────────────────────────────────────────────────
# find_by_session_id
# ─────────────────────────────────────────────────────────────────────────────

class TestFindBySessionId:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_empty_list_when_none_found(self, repo, mock_collection):
        mock_collection.find.return_value = iter([])
        result = repo.find_by_session_id("session-x")
        assert result == []

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_queries_by_session_id_field(self, repo, mock_collection):
        mock_collection.find.return_value = iter([])
        repo.find_by_session_id("sess-abc")
        mock_collection.find.assert_called_with({"session_id": "sess-abc"})

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_list_of_entities(self, repo, mock_collection, sample_token_doc):
        mock_collection.find.return_value = iter([sample_token_doc, sample_token_doc])
        result = repo.find_by_session_id("session-uuid-0001")
        assert len(result) == 2
        assert all(isinstance(t, RefreshToken) for t in result)

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_wraps_pymongo_error(self, repo, mock_collection):
        mock_collection.find.side_effect = PyMongoError("cursor error")
        with pytest.raises(RepositoryError):
            repo.find_by_session_id("s")


# ─────────────────────────────────────────────────────────────────────────────
# revoke_session
# ─────────────────────────────────────────────────────────────────────────────

class TestRevokeSession:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_calls_update_many_with_session_filter(self, repo, mock_collection):
        mock_collection.update_many.return_value = MagicMock(modified_count=2)
        repo.revoke_session("sess-123", "logout")
        call_args = mock_collection.update_many.call_args
        query_filter = call_args[0][0]
        assert query_filter["session_id"] == "sess-123"
        assert query_filter["revoked_at"] is None

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_sets_revoked_at_and_reason_in_update(self, repo, mock_collection):
        mock_collection.update_many.return_value = MagicMock(modified_count=1)
        repo.revoke_session("sess-123", "stolen")
        update_op = mock_collection.update_many.call_args[0][1]
        assert "revoked_at" in update_op["$set"]
        assert update_op["$set"]["revoked_reason"] == "stolen"

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_modified_count(self, repo, mock_collection):
        mock_collection.update_many.return_value = MagicMock(modified_count=3)
        count = repo.revoke_session("sess-456", "reason")
        assert count == 3

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_zero_when_no_active_tokens(self, repo, mock_collection):
        mock_collection.update_many.return_value = MagicMock(modified_count=0)
        assert repo.revoke_session("empty-session", "reason") == 0

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_wraps_pymongo_error(self, repo, mock_collection):
        mock_collection.update_many.side_effect = PyMongoError("write error")
        with pytest.raises(RepositoryError):
            repo.revoke_session("s", "r")


# ─────────────────────────────────────────────────────────────────────────────
# delete_expired
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteExpired:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_calls_delete_many_with_expires_at_filter(self, repo, mock_collection):
        mock_collection.delete_many.return_value = MagicMock(deleted_count=0)
        repo.delete_expired()
        call_args = mock_collection.delete_many.call_args
        query_filter = call_args[0][0]
        assert "expires_at" in query_filter
        assert "$lte" in query_filter["expires_at"]

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_deleted_count(self, repo, mock_collection):
        mock_collection.delete_many.return_value = MagicMock(deleted_count=5)
        assert repo.delete_expired() == 5

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_zero_when_no_expired_tokens(self, repo, mock_collection):
        mock_collection.delete_many.return_value = MagicMock(deleted_count=0)
        assert repo.delete_expired() == 0

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_wraps_pymongo_error(self, repo, mock_collection):
        mock_collection.delete_many.side_effect = PyMongoError("delete error")
        with pytest.raises(RepositoryError):
            repo.delete_expired()


# ─────────────────────────────────────────────────────────────────────────────
# save (inherited — verify token-specific document shape)
# ─────────────────────────────────────────────────────────────────────────────

class TestSaveToken:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_save_includes_required_token_fields(
        self, repo, mock_collection, sample_refresh_token
    ):
        repo.save(sample_refresh_token)
        doc = mock_collection.replace_one.call_args[0][1]
        for field in ("token_hash", "user_id", "session_id", "expires_at"):
            assert field in doc, f"Missing field: {field}"

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_save_uses_token_id_as_document_id(
        self, repo, mock_collection, sample_refresh_token
    ):
        repo.save(sample_refresh_token)
        filter_doc = mock_collection.replace_one.call_args[0][0]
        assert filter_doc == {"_id": sample_refresh_token.id}


# ─────────────────────────────────────────────────────────────────────────────
# _to_entity (document → entity)
# ─────────────────────────────────────────────────────────────────────────────

class TestToEntity:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_reconstructs_all_fields(self, repo, sample_token_doc):
        token = repo._to_entity(sample_token_doc)
        assert token.id == sample_token_doc["_id"]
        assert token.token_hash == sample_token_doc["token_hash"]
        assert token.user_id == sample_token_doc["user_id"]
        assert token.session_id == sample_token_doc["session_id"]
        assert token.expires_at == sample_token_doc["expires_at"]

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_nullable_fields_default_to_none(self, repo):
        now = datetime.now(timezone.utc)
        doc = {
            "_id": "t1",
            "token_hash": "hash",
            "user_id": "u1",
            "session_id": "s1",
            "expires_at": now + timedelta(days=7),
            "created_at": now,
        }
        token = repo._to_entity(doc)
        assert token.used_at is None
        assert token.revoked_at is None
        assert token.revoked_reason is None
        assert token.replaced_by_id is None
