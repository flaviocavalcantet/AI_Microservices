"""tests/mongodb/unit/test_mongo_metrics.py

Layer 2 — MongoMetrics counter and thread-safety tests.

All tests are pure in-memory with zero I/O.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

import pytest

from shared.shared_infrastructure.src.mongodb.connection import MongoMetrics


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def metrics() -> MongoMetrics:
    return MongoMetrics()


# ─────────────────────────────────────────────────────────────────────────────
# Initial state
# ─────────────────────────────────────────────────────────────────────────────

class TestInitialState:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_all_counters_start_at_zero(self, metrics: MongoMetrics):
        assert metrics.connect_attempts == 0
        assert metrics.connect_successes == 0
        assert metrics.connect_failures == 0
        assert metrics.reconnect_attempts == 0
        assert metrics.total_operations == 0
        assert metrics.failed_operations == 0

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_avg_latency_is_none_before_any_ops(self, metrics: MongoMetrics):
        assert metrics.avg_latency_ms is None

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_timestamps_are_none_initially(self, metrics: MongoMetrics):
        assert metrics.connected_at is None
        assert metrics.last_ping_at is None
        assert metrics.last_ping_ok is None


# ─────────────────────────────────────────────────────────────────────────────
# record_connect_attempt
# ─────────────────────────────────────────────────────────────────────────────

class TestRecordConnectAttempt:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_success_increments_successes(self, metrics: MongoMetrics):
        metrics.record_connect_attempt(success=True)
        assert metrics.connect_attempts == 1
        assert metrics.connect_successes == 1
        assert metrics.connect_failures == 0

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_failure_increments_failures(self, metrics: MongoMetrics):
        metrics.record_connect_attempt(success=False)
        assert metrics.connect_attempts == 1
        assert metrics.connect_failures == 1
        assert metrics.connect_successes == 0

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_success_sets_connected_at_timestamp(self, metrics: MongoMetrics):
        before = datetime.now(timezone.utc)
        metrics.record_connect_attempt(success=True)
        assert metrics.connected_at is not None
        assert metrics.connected_at >= before

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_failure_does_not_set_connected_at(self, metrics: MongoMetrics):
        metrics.record_connect_attempt(success=False)
        assert metrics.connected_at is None


# ─────────────────────────────────────────────────────────────────────────────
# record_op
# ─────────────────────────────────────────────────────────────────────────────

class TestRecordOp:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_successful_op_increments_total_only(self, metrics: MongoMetrics):
        metrics.record_op(latency_ms=10.0, success=True)
        assert metrics.total_operations == 1
        assert metrics.failed_operations == 0

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_failed_op_increments_both_totals(self, metrics: MongoMetrics):
        metrics.record_op(latency_ms=5.0, success=False)
        assert metrics.total_operations == 1
        assert metrics.failed_operations == 1

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_avg_latency_single_op(self, metrics: MongoMetrics):
        metrics.record_op(latency_ms=20.0)
        assert metrics.avg_latency_ms == 20.0

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_avg_latency_multiple_ops(self, metrics: MongoMetrics):
        metrics.record_op(latency_ms=10.0)
        metrics.record_op(latency_ms=30.0)
        assert metrics.avg_latency_ms == 20.0

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_avg_latency_rounded_to_two_decimals(self, metrics: MongoMetrics):
        metrics.record_op(latency_ms=10.0)
        metrics.record_op(latency_ms=20.0)
        metrics.record_op(latency_ms=30.0)
        # avg = 20.0 exactly here; test rounding with 1/3
        m2 = MongoMetrics()
        m2.record_op(1.0)
        m2.record_op(2.0)
        m2.record_op(3.0)
        assert isinstance(m2.avg_latency_ms, float)
        # 2 decimal places precision enforced
        assert m2.avg_latency_ms == round(m2.avg_latency_ms, 2)


# ─────────────────────────────────────────────────────────────────────────────
# record_ping
# ─────────────────────────────────────────────────────────────────────────────

class TestRecordPing:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_successful_ping_sets_ok_true(self, metrics: MongoMetrics):
        metrics.record_ping(ok=True)
        assert metrics.last_ping_ok is True

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_failed_ping_sets_ok_false(self, metrics: MongoMetrics):
        metrics.record_ping(ok=False)
        assert metrics.last_ping_ok is False

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_ping_sets_last_ping_at(self, metrics: MongoMetrics):
        before = datetime.now(timezone.utc)
        metrics.record_ping(ok=True)
        assert metrics.last_ping_at is not None
        assert metrics.last_ping_at >= before


# ─────────────────────────────────────────────────────────────────────────────
# record_reconnect
# ─────────────────────────────────────────────────────────────────────────────

class TestRecordReconnect:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_increments_reconnect_counter(self, metrics: MongoMetrics):
        metrics.record_reconnect()
        metrics.record_reconnect()
        assert metrics.reconnect_attempts == 2


# ─────────────────────────────────────────────────────────────────────────────
# to_dict serialization
# ─────────────────────────────────────────────────────────────────────────────

class TestToDict:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_to_dict_contains_all_keys(self, metrics: MongoMetrics):
        d = metrics.to_dict()
        expected_keys = {
            "connect_attempts", "connect_successes", "connect_failures",
            "reconnect_attempts", "total_operations", "failed_operations",
            "avg_latency_ms", "connected_at", "last_ping_at", "last_ping_ok",
        }
        assert expected_keys.issubset(d.keys())

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_to_dict_timestamps_as_iso_string_or_none(self, metrics: MongoMetrics):
        metrics.record_connect_attempt(success=True)
        d = metrics.to_dict()
        assert isinstance(d["connected_at"], str)
        assert d["last_ping_at"] is None  # not pinged yet

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_to_dict_snapshot_is_independent(self, metrics: MongoMetrics):
        d1 = metrics.to_dict()
        metrics.record_op(10.0)
        d2 = metrics.to_dict()
        assert d1["total_operations"] == 0
        assert d2["total_operations"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# Thread safety
# ─────────────────────────────────────────────────────────────────────────────

class TestThreadSafety:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_concurrent_record_op_produces_correct_totals(self):
        """100 threads each recording 10 ops → exactly 1000 total_operations."""
        metrics = MongoMetrics()
        threads = [
            threading.Thread(
                target=lambda: [metrics.record_op(1.0) for _ in range(10)]
            )
            for _ in range(100)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert metrics.total_operations == 1000

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_concurrent_record_connect_attempt(self):
        """50 threads each recording one success → exactly 50 successes."""
        metrics = MongoMetrics()
        threads = [
            threading.Thread(target=lambda: metrics.record_connect_attempt(success=True))
            for _ in range(50)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert metrics.connect_successes == 50
        assert metrics.connect_attempts == 50
