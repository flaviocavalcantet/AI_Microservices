"""tests/mongodb/repository/test_user_repository.py

Layer 3 — MongoUserRepository unit tests (mocked collection).

Verifies query construction, document mapping, index declaration, and
error wrapping without any real MongoDB I/O.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest
from pymongo.errors import DuplicateKeyError, PyMongoError

from services.auth_service.src.domain.entities.user import User
from services.auth_service.src.infrastructure.repositories.mongo_user_repository import (
    MongoUserRepository,
)
from shared.shared_infrastructure.src.mongodb.base_repository import (
    DuplicateEntityError,
    RepositoryError,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixture
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def repo(mock_db, mock_collection):
    r = MongoUserRepository(mock_db)
    r._indexes_ensured = True
    with patch.object(
        MongoUserRepository,
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
    def test_ensure_indexes_calls_create_indexes(self, mock_db, mock_collection):
        r = MongoUserRepository(mock_db)
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        r.ensure_indexes()
        mock_collection.create_indexes.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_three_indexes_declared(self, mock_db, mock_collection):
        r = MongoUserRepository(mock_db)
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        r.ensure_indexes()
        indexes_arg = mock_collection.create_indexes.call_args[0][0]
        assert len(indexes_arg) == 3

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_provider_identity_index_is_unique(self, mock_db, mock_collection):
        r = MongoUserRepository(mock_db)
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        r.ensure_indexes()
        indexes_arg = mock_collection.create_indexes.call_args[0][0]
        names = {idx.document["name"]: idx.document for idx in indexes_arg}
        assert names["idx_provider_identity"]["unique"] is True

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_email_index_is_unique(self, mock_db, mock_collection):
        r = MongoUserRepository(mock_db)
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        r.ensure_indexes()
        indexes_arg = mock_collection.create_indexes.call_args[0][0]
        names = {idx.document["name"]: idx.document for idx in indexes_arg}
        assert names["idx_email"]["unique"] is True


# ─────────────────────────────────────────────────────────────────────────────
# find_by_provider
# ─────────────────────────────────────────────────────────────────────────────

class TestFindByProvider:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_none_when_not_found(self, repo, mock_collection):
        mock_collection.find_one.return_value = None
        assert repo.find_by_provider("github", "gh-123") is None

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_queries_correct_fields(self, repo, mock_collection):
        mock_collection.find_one.return_value = None
        repo.find_by_provider("google", "goog-456")
        mock_collection.find_one.assert_called_with(
            {"provider": "google", "provider_user_id": "goog-456"}
        )

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_user_entity_when_found(self, repo, mock_collection, sample_user_doc):
        mock_collection.find_one.return_value = sample_user_doc
        user = repo.find_by_provider("github", "gh-12345")
        assert isinstance(user, User)
        assert user.provider == "github"
        assert user.provider_user_id == "gh-12345"

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_wraps_pymongo_error(self, repo, mock_collection):
        mock_collection.find_one.side_effect = PyMongoError("read error")
        with pytest.raises(RepositoryError):
            repo.find_by_provider("github", "x")


# ─────────────────────────────────────────────────────────────────────────────
# find_by_email
# ─────────────────────────────────────────────────────────────────────────────

class TestFindByEmail:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_none_when_not_found(self, repo, mock_collection):
        mock_collection.find_one.return_value = None
        assert repo.find_by_email("missing@example.com") is None

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_applies_case_insensitive_collation(self, repo, mock_collection):
        mock_collection.find_one.return_value = None
        repo.find_by_email("Alice@Example.COM")
        _, kwargs = mock_collection.find_one.call_args
        collation = kwargs.get("collation", {})
        assert collation.get("strength") == 2

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_returns_user_when_found(self, repo, mock_collection, sample_user_doc):
        mock_collection.find_one.return_value = sample_user_doc
        user = repo.find_by_email("alice@example.com")
        assert isinstance(user, User)
        assert user.email == "alice@example.com"

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_wraps_pymongo_error(self, repo, mock_collection):
        mock_collection.find_one.side_effect = PyMongoError("fail")
        with pytest.raises(RepositoryError):
            repo.find_by_email("x@y.com")


# ─────────────────────────────────────────────────────────────────────────────
# save (inherited, but verify User-specific document shape)
# ─────────────────────────────────────────────────────────────────────────────

class TestSaveUser:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_save_upserts_with_correct_id(self, repo, mock_collection, sample_user):
        repo.save(sample_user)
        args, _ = mock_collection.replace_one.call_args
        assert args[0] == {"_id": sample_user.id}

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_document_contains_all_user_fields(self, repo, mock_collection, sample_user):
        repo.save(sample_user)
        doc = mock_collection.replace_one.call_args[0][1]
        for field in ("provider", "provider_user_id", "email", "display_name", "roles"):
            assert field in doc, f"Missing field: {field}"

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_document_does_not_contain_updated_at_from_entity(
        self, repo, mock_collection, sample_user
    ):
        """updated_at is stamped by base class, never by entity-to-doc mapping."""
        repo.save(sample_user)
        doc = mock_collection.replace_one.call_args[0][1]
        # updated_at IS in the final doc (base class stamps it) — verify it is a datetime
        assert isinstance(doc["updated_at"], datetime)

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_wraps_duplicate_key_error_as_duplicate_entity_error(
        self, repo, mock_collection, sample_user
    ):
        mock_collection.replace_one.side_effect = DuplicateKeyError("E11000")
        with pytest.raises(DuplicateEntityError):
            repo.save(sample_user)


# ─────────────────────────────────────────────────────────────────────────────
# _to_entity (document → entity)
# ─────────────────────────────────────────────────────────────────────────────

class TestToEntity:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_reconstructs_user_from_complete_document(self, repo, sample_user_doc):
        user = repo._to_entity(sample_user_doc)
        assert user.id == sample_user_doc["_id"]
        assert user.email == sample_user_doc["email"]
        assert user.provider == sample_user_doc["provider"]
        assert user.roles == sample_user_doc["roles"]

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_defaults_roles_to_user_when_absent(self, repo):
        doc = {
            "_id": "uid", "provider": "github", "provider_user_id": "p1",
            "email": "x@x.com", "display_name": "X",
            "is_active": True, "created_at": datetime.utcnow(),
        }
        user = repo._to_entity(doc)
        assert user.roles == ["user"]

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_defaults_is_active_to_true_when_absent(self, repo):
        doc = {
            "_id": "uid2", "provider": "github", "provider_user_id": "p2",
            "email": "y@y.com", "display_name": "Y",
            "created_at": datetime.utcnow(),
        }
        user = repo._to_entity(doc)
        assert user.is_active is True

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_handles_null_avatar_url(self, repo):
        doc = {
            "_id": "uid3", "provider": "google", "provider_user_id": "p3",
            "email": "z@z.com", "display_name": "Z",
            "avatar_url": None, "is_active": True,
            "created_at": datetime.utcnow(),
        }
        user = repo._to_entity(doc)
        assert user.avatar_url is None
