"""tests/mongodb/integration/test_refresh_token_repo_integration.py

Layer 4 — MongoRefreshTokenRepository integration tests against mongomock.

Covers full CRUD round-trips, session revocation, housekeeping (delete_expired),
and the TTL index declaration — all without network I/O.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from freezegun import freeze_time

from services.auth_service.src.domain.entities.refresh_token import RefreshToken
from shared.shared_infrastructure.src.mongodb.base_repository import RepositoryError
from tests.mongodb.conftest import make_token
from tests.mongodb.integration.conftest import skip_if_no_mongomock


pytestmark = [pytest.mark.integration, pytest.mark.mongodb, skip_if_no_mongomock]

_BASE_TIME = "2026-01-15 10:00:00"


# ─────────────────────────────────────────────────────────────────────────────
# Save & find_by_hash round-trip
# ─────────────────────────────────────────────────────────────────────────────

class TestSaveAndFindByHash:
    def test_save_and_retrieve_token(self, token_repo):
        token = make_token()
        token_repo.save(token)
        found = token_repo.find_by_hash(token.token_hash)
        assert found is not None
        assert found.id == token.id

    def test_find_by_hash_returns_none_when_missing(self, token_repo):
        assert token_repo.find_by_hash("no-such-hash") is None

    def test_all_fields_preserved_on_round_trip(self, token_repo):
        token = make_token(user_id="uid-abc", session_id="sess-xyz")
        token_repo.save(token)
        found = token_repo.find_by_hash(token.token_hash)
        assert found.user_id == "uid-abc"
        assert found.session_id == "sess-xyz"
        assert found.expires_at == token.expires_at

    def test_nullable_fields_are_none_on_fresh_token(self, token_repo):
        token = make_token()
        token_repo.save(token)
        found = token_repo.find_by_hash(token.token_hash)
        assert found.used_at is None
        assert found.revoked_at is None
        assert found.revoked_reason is None
        assert found.replaced_by_id is None

    def test_save_upsert_updates_existing_token(self, token_repo):
        token = make_token()
        token_repo.save(token)
        token.revoked_at = datetime(2026, 1, 15, 11, 0, 0)
        token.revoked_reason = "test_update"
        token_repo.save(token)
        found = token_repo.find_by_hash(token.token_hash)
        assert found.revoked_reason == "test_update"


# ─────────────────────────────────────────────────────────────────────────────
# find_by_session_id
# ─────────────────────────────────────────────────────────────────────────────

class TestFindBySessionId:
    def test_returns_all_tokens_in_session(self, token_repo):
        session = "sess-family-1"
        t1 = make_token(session_id=session)
        t2 = make_token(session_id=session)
        token_repo.save(t1)
        token_repo.save(t2)
        result = token_repo.find_by_session_id(session)
        assert len(result) == 2

    def test_returns_empty_list_for_unknown_session(self, token_repo):
        assert token_repo.find_by_session_id("ghost-session") == []

    def test_does_not_return_tokens_from_other_sessions(self, token_repo):
        t_in = make_token(session_id="sess-A")
        t_out = make_token(session_id="sess-B")
        token_repo.save(t_in)
        token_repo.save(t_out)
        result = token_repo.find_by_session_id("sess-A")
        assert all(t.session_id == "sess-A" for t in result)


# ─────────────────────────────────────────────────────────────────────────────
# revoke_session
# ─────────────────────────────────────────────────────────────────────────────

class TestRevokeSession:
    def test_revokes_all_active_tokens_in_session(self, token_repo):
        session = "sess-revoke"
        t1 = make_token(session_id=session)
        t2 = make_token(session_id=session)
        token_repo.save(t1)
        token_repo.save(t2)

        count = token_repo.revoke_session(session, "logout")
        assert count == 2

        # Verify the revocation was persisted
        tokens = token_repo.find_by_session_id(session)
        assert all(t.revoked_at is not None for t in tokens)
        assert all(t.revoked_reason == "logout" for t in tokens)

    def test_does_not_revoke_already_revoked_tokens(self, token_repo):
        session = "sess-partial"
        t_active = make_token(session_id=session)
        t_revoked = make_token(session_id=session, revoked=True)
        token_repo.save(t_active)
        token_repo.save(t_revoked)

        count = token_repo.revoke_session(session, "reason")
        # Only the active token should be modified
        assert count == 1

    def test_returns_zero_when_no_tokens_in_session(self, token_repo):
        count = token_repo.revoke_session("empty-sess", "logout")
        assert count == 0

    def test_revocation_does_not_affect_other_sessions(self, token_repo):
        t_target = make_token(session_id="sess-target")
        t_other = make_token(session_id="sess-safe")
        token_repo.save(t_target)
        token_repo.save(t_other)

        token_repo.revoke_session("sess-target", "logout")

        safe_tokens = token_repo.find_by_session_id("sess-safe")
        assert all(t.revoked_at is None for t in safe_tokens)


# ─────────────────────────────────────────────────────────────────────────────
# delete_expired
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteExpired:
    @freeze_time(_BASE_TIME)
    def test_deletes_expired_tokens(self, token_repo):
        expired = make_token(expired=True)
        valid = make_token()
        token_repo.save(expired)
        token_repo.save(valid)

        count = token_repo.delete_expired()
        assert count == 1
        assert token_repo.find_by_hash(expired.token_hash) is None
        assert token_repo.find_by_hash(valid.token_hash) is not None

    @freeze_time(_BASE_TIME)
    def test_returns_zero_when_no_expired_tokens(self, token_repo):
        valid = make_token()
        token_repo.save(valid)
        assert token_repo.delete_expired() == 0

    @freeze_time(_BASE_TIME)
    def test_deletes_multiple_expired_tokens(self, token_repo):
        tokens = [make_token(expired=True) for _ in range(3)]
        for t in tokens:
            token_repo.save(t)
        assert token_repo.delete_expired() == 3


# ─────────────────────────────────────────────────────────────────────────────
# delete & exists
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteAndExists:
    def test_exists_true_after_save(self, token_repo):
        token = make_token()
        token_repo.save(token)
        assert token_repo.exists(token.id) is True

    def test_delete_removes_token(self, token_repo):
        token = make_token()
        token_repo.save(token)
        assert token_repo.delete(token.id) is True
        assert token_repo.find_by_hash(token.token_hash) is None

    def test_delete_returns_false_for_missing_token(self, token_repo):
        assert token_repo.delete("nonexistent-id") is False


# ─────────────────────────────────────────────────────────────────────────────
# Unique index: token_hash
# ─────────────────────────────────────────────────────────────────────────────

class TestTokenHashUniqueIndex:
    def test_duplicate_token_hash_raises(self, token_repo):
        t1 = make_token()
        t2 = make_token()
        t2.token_hash = t1.token_hash  # force collision
        token_repo.save(t1)
        with pytest.raises(Exception):  # DuplicateEntityError or pymongo DuplicateKeyError
            token_repo.save(t2)
