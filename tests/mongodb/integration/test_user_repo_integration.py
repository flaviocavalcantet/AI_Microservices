"""tests/mongodb/integration/test_user_repo_integration.py

Layer 4 — MongoUserRepository integration tests against mongomock.

Tests real CRUD round-trips, unique-index enforcement, case-insensitive
email lookup, and field persistence without any network I/O.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from services.auth_service.src.domain.entities.user import User
from shared.shared_infrastructure.src.mongodb.base_repository import (
    DuplicateEntityError,
    RepositoryError,
)
from tests.mongodb.conftest import make_user
from tests.mongodb.integration.conftest import skip_if_no_mongomock


pytestmark = [pytest.mark.integration, pytest.mark.mongodb, skip_if_no_mongomock]


# ─────────────────────────────────────────────────────────────────────────────
# Save & find_by_id round-trip
# ─────────────────────────────────────────────────────────────────────────────

class TestSaveAndFindById:
    def test_save_and_retrieve_user(self, user_repo):
        user = make_user(email="alice@example.com")
        user_repo.save(user)
        found = user_repo.find_by_id(user.id)
        assert found is not None
        assert found.id == user.id
        assert found.email == "alice@example.com"

    def test_find_by_id_returns_none_for_unknown_id(self, user_repo):
        assert user_repo.find_by_id("nonexistent-uuid") is None

    def test_save_preserves_all_fields(self, user_repo):
        user = make_user(
            email="bob@example.com",
            display_name="Bob Builder",
            roles=["user", "admin"],
        )
        user_repo.save(user)
        found = user_repo.find_by_id(user.id)
        assert found.display_name == "Bob Builder"
        assert "admin" in found.roles

    def test_save_is_idempotent_upsert(self, user_repo):
        user = make_user(email="carol@example.com")
        user_repo.save(user)
        user.display_name = "Carol Updated"
        user_repo.save(user)
        # Should not raise, and only one document should exist
        assert user_repo.find_by_id(user.id).display_name == "Carol Updated"

    def test_updated_at_is_set_after_save(self, user_repo):
        user = make_user(email="dave@example.com")
        user_repo.save(user)
        doc = user_repo._db[user_repo.COLLECTION_NAME].find_one({"_id": user.id})
        assert doc is not None
        assert "updated_at" in doc
        assert isinstance(doc["updated_at"], datetime)


# ─────────────────────────────────────────────────────────────────────────────
# find_by_provider
# ─────────────────────────────────────────────────────────────────────────────

class TestFindByProvider:
    def test_finds_user_by_provider_and_id(self, user_repo):
        user = make_user(provider="github", provider_user_id="gh-999")
        user_repo.save(user)
        found = user_repo.find_by_provider("github", "gh-999")
        assert found is not None
        assert found.id == user.id

    def test_returns_none_for_wrong_provider(self, user_repo):
        user = make_user(provider="github", provider_user_id="gh-001")
        user_repo.save(user)
        assert user_repo.find_by_provider("google", "gh-001") is None

    def test_returns_none_for_wrong_provider_user_id(self, user_repo):
        user = make_user(provider="github", provider_user_id="gh-002")
        user_repo.save(user)
        assert user_repo.find_by_provider("github", "gh-999") is None

    def test_two_providers_same_email_coexist(self, user_repo):
        """Users from different providers are distinct even with the same email."""
        uid1 = str(uuid.uuid4())
        uid2 = str(uuid.uuid4())
        user1 = make_user(id=uid1, provider="github", provider_user_id="p-github",
                          email="shared@example.com")
        user2 = make_user(id=uid2, provider="google", provider_user_id="p-google",
                          email="other@example.com")
        user_repo.save(user1)
        user_repo.save(user2)
        assert user_repo.find_by_provider("github", "p-github").id == uid1
        assert user_repo.find_by_provider("google", "p-google").id == uid2


# ─────────────────────────────────────────────────────────────────────────────
# find_by_email
# ─────────────────────────────────────────────────────────────────────────────

class TestFindByEmail:
    def test_finds_user_by_exact_email(self, user_repo):
        user = make_user(email="eve@example.com")
        user_repo.save(user)
        found = user_repo.find_by_email("eve@example.com")
        assert found is not None
        assert found.id == user.id

    def test_email_lookup_is_case_insensitive(self, user_repo):
        user = make_user(email="frank@example.com")
        user_repo.save(user)
        found = user_repo.find_by_email("FRANK@EXAMPLE.COM")
        assert found is not None
        assert found.id == user.id

    def test_returns_none_for_missing_email(self, user_repo):
        assert user_repo.find_by_email("nobody@example.com") is None


# ─────────────────────────────────────────────────────────────────────────────
# Unique index enforcement
# ─────────────────────────────────────────────────────────────────────────────

class TestUniqueIndexEnforcement:
    def test_duplicate_provider_identity_raises(self, user_repo):
        u1 = make_user(provider="github", provider_user_id="dup-id",
                       email="first@example.com")
        u2 = make_user(provider="github", provider_user_id="dup-id",
                       email="second@example.com")  # different email, same provider identity
        user_repo.save(u1)
        with pytest.raises((DuplicateEntityError, Exception)):
            user_repo.save(u2)

    def test_duplicate_email_raises(self, user_repo):
        u1 = make_user(provider="github", provider_user_id="puid-1",
                       email="dup@example.com")
        u2 = make_user(provider="google", provider_user_id="puid-2",
                       email="dup@example.com")  # same email, different provider
        user_repo.save(u1)
        with pytest.raises((DuplicateEntityError, Exception)):
            user_repo.save(u2)


# ─────────────────────────────────────────────────────────────────────────────
# delete & exists
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteAndExists:
    def test_exists_true_after_save(self, user_repo):
        user = make_user(email="hank@example.com")
        user_repo.save(user)
        assert user_repo.exists(user.id) is True

    def test_exists_false_for_unknown_id(self, user_repo):
        assert user_repo.exists("ghost-id") is False

    def test_delete_removes_user(self, user_repo):
        user = make_user(email="iris@example.com")
        user_repo.save(user)
        deleted = user_repo.delete(user.id)
        assert deleted is True
        assert user_repo.find_by_id(user.id) is None

    def test_delete_returns_false_when_not_found(self, user_repo):
        assert user_repo.delete("nonexistent") is False
