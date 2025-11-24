from datetime import datetime, timezone
from uuid import uuid4

import pytest

from pharox.models import (
    AcquireEventPayload,
    Lease,
    PoolStatsSnapshot,
    ReleaseEventPayload,
    SelectorStrategy,
)
from pharox.observability import metrics as metrics_module
from pharox.observability.metrics import PrometheusMetricsRecorder


class _StubMetricChild:
    def __init__(self):
        self.count = 0
        self.observations = []
        self.last_set = None

    def inc(self, amount: int = 1):
        self.count += amount

    def observe(self, value: float):
        self.observations.append(value)

    def set(self, value):
        self.last_set = value


class _StubMetric:
    def __init__(self, *args, **kwargs):
        self.children = {}

    def labels(self, **labels):
        key = tuple(sorted(labels.items()))
        child = self.children.get(key)
        if child is None:
            child = _StubMetricChild()
            self.children[key] = child
        return child


class _StubPrometheusClient:
    Counter = _StubMetric
    Histogram = _StubMetric
    Gauge = _StubMetric


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
        total_proxies=4,
        active_proxies=3,
        available_proxies=2,
        leased_proxies=1,
        total_leases=10,
    )


def _acquire_payload(hit: bool = True):
    now = datetime.now(timezone.utc)
    return AcquireEventPayload(
        lease=_lease() if hit else None,
        pool_name="alpha",
        consumer_name="worker-a",
        filters=None,
        selector=SelectorStrategy.ROUND_ROBIN,
        started_at=now,
        completed_at=now,
        duration_ms=25,
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
        lease_duration_ms=75,
        pool_stats=_pool_stats(),
    )


@pytest.fixture(autouse=True)
def stub_prometheus(monkeypatch):
    monkeypatch.setattr(metrics_module, "prometheus_client", _StubPrometheusClient())
    yield


def test_acquire_metrics_are_recorded():
    recorder = PrometheusMetricsRecorder(namespace="test")
    payload = _acquire_payload()

    recorder.handle_acquire(payload)

    key = (
        ("consumer", payload.consumer_name),
        ("pool", payload.pool_name),
        ("selector", payload.selector.value),
        ("status", "hit"),
    )
    counter = recorder._acquire_total.children[tuple(sorted(key))]
    assert counter.count == 1

    histogram = recorder._acquire_duration_seconds.children[tuple(sorted(key))]
    assert histogram.observations == [pytest.approx(payload.duration_ms / 1000)]

    available = recorder._available_gauge.children[(("pool", payload.pool_name),)]
    assert available.last_set == payload.pool_stats.available_proxies


def test_release_metrics_are_recorded():
    recorder = PrometheusMetricsRecorder(namespace="test")
    payload = _release_payload()

    recorder.handle_release(payload)

    key = (("pool", payload.pool_name),)
    counter = recorder._release_total.children[tuple(sorted(key))]
    assert counter.count == 1

    histogram = recorder._lease_duration_seconds.children[tuple(sorted(key))]
    assert histogram.observations == [
        pytest.approx(payload.lease_duration_ms / 1000)
    ]
