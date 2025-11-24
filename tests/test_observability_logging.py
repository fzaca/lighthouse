from datetime import datetime, timezone
from uuid import uuid4

from pharox.models import (
    AcquireEventPayload,
    Lease,
    PoolStatsSnapshot,
    ReleaseEventPayload,
    SelectorStrategy,
)
from pharox.observability.logging import StructuredLogger


class _FakeLogger:
    def __init__(self):
        self.records = []

    def info(self, message, extra=None):
        self.records.append({"message": message, "extra": extra})


def _lease():
    now = datetime.now(timezone.utc)
    return Lease(
        id=uuid4(),
        proxy_id=uuid4(),
        consumer_id=uuid4(),
        pool_id=uuid4(),
        pool_name="alpha",
        expires_at=now,
        acquired_at=now,
    )


def _pool_stats():
    return PoolStatsSnapshot(
        pool_name="alpha",
        total_proxies=3,
        active_proxies=3,
        available_proxies=2,
        leased_proxies=1,
        total_leases=8,
    )


def _acquire_payload():
    now = datetime.now(timezone.utc)
    return AcquireEventPayload(
        lease=_lease(),
        pool_name="alpha",
        consumer_name="worker-a",
        filters=None,
        selector=SelectorStrategy.LEAST_USED,
        started_at=now,
        completed_at=now,
        duration_ms=12,
        pool_stats=_pool_stats(),
    )


def _release_payload():
    now = datetime.now(timezone.utc)
    lease = _lease()
    lease.released_at = now
    return ReleaseEventPayload(
        lease=lease,
        pool_name="alpha",
        released_at=now,
        lease_duration_ms=35,
        pool_stats=_pool_stats(),
    )


def test_structured_logger_emits_acquire_records():
    logger = _FakeLogger()
    structured = StructuredLogger(logger=logger, random_fn=lambda: 0.0)

    structured.handle_acquire(_acquire_payload())

    assert len(logger.records) == 1
    record = logger.records[0]["extra"]
    assert record["event"] == "pharox.acquire"
    assert record["status"] == "hit"
    assert record["selector"] == SelectorStrategy.LEAST_USED.value
    assert record["pool_stats"]["available_proxies"] == 2


def test_structured_logger_respects_sampling():
    logger = _FakeLogger()
    structured = StructuredLogger(
        logger=logger, sample_rate=0.0, random_fn=lambda: 0.5
    )

    structured.handle_acquire(_acquire_payload())
    structured.handle_release(_release_payload())

    assert logger.records == []


def test_structured_logger_emits_release_records():
    logger = _FakeLogger()
    structured = StructuredLogger(logger=logger, random_fn=lambda: 0.0)

    structured.handle_release(_release_payload())

    assert len(logger.records) == 1
    record = logger.records[0]["extra"]
    assert record["event"] == "pharox.release"
    assert record["lease_duration_ms"] == 35
    assert record["pool_stats"]["pool"] == "alpha"
