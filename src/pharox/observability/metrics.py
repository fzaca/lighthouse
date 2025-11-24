from __future__ import annotations

from typing import Optional, Sequence

from pharox.models import (
    AcquireEventPayload,
    PoolStatsSnapshot,
    ReleaseEventPayload,
)

try:  # pragma: no cover - exercised through tests via monkeypatch
    import prometheus_client  # type: ignore
except ImportError:  # pragma: no cover
    prometheus_client = None


DEFAULT_LATENCY_BUCKETS: Sequence[float] = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)


def _require_prometheus_client():
    if prometheus_client is None:
        raise ImportError(
            "prometheus-client is required for PrometheusMetricsRecorder. "
            "Install with `pip install pharox[observability]`."
        )
    return prometheus_client


class PrometheusMetricsRecorder:
    """Translate lifecycle callbacks into Prometheus counters and histograms."""

    def __init__(
        self,
        *,
        registry: Optional[object] = None,
        namespace: str = "pharox",
        acquire_buckets: Optional[Sequence[float]] = None,
        lease_buckets: Optional[Sequence[float]] = None,
    ) -> None:
        client = _require_prometheus_client()
        acquire_latency = tuple(acquire_buckets or DEFAULT_LATENCY_BUCKETS)
        lease_latency = tuple(lease_buckets or DEFAULT_LATENCY_BUCKETS)

        self._acquire_total = client.Counter(
            "acquire_total",
            "Total proxy acquisition attempts.",
            labelnames=("pool", "consumer", "selector", "status"),
            namespace=namespace,
            registry=registry,
        )
        self._acquire_duration_seconds = client.Histogram(
            "acquire_duration_seconds",
            "Latency for proxy acquisition attempts.",
            labelnames=("pool", "consumer", "selector", "status"),
            namespace=namespace,
            registry=registry,
            buckets=acquire_latency,
        )
        self._release_total = client.Counter(
            "release_total",
            "Total proxy release attempts.",
            labelnames=("pool",),
            namespace=namespace,
            registry=registry,
        )
        self._lease_duration_seconds = client.Histogram(
            "lease_duration_seconds",
            "Observed lease durations from acquire to release.",
            labelnames=("pool",),
            namespace=namespace,
            registry=registry,
            buckets=lease_latency,
        )
        self._available_gauge = client.Gauge(
            "pool_available_proxies",
            "Currently available proxies in the pool.",
            labelnames=("pool",),
            namespace=namespace,
            registry=registry,
        )
        self._active_gauge = client.Gauge(
            "pool_active_proxies",
            "Active proxies in the pool.",
            labelnames=("pool",),
            namespace=namespace,
            registry=registry,
        )
        self._leased_gauge = client.Gauge(
            "pool_leased_proxies",
            "Number of in-flight leases per pool.",
            labelnames=("pool",),
            namespace=namespace,
            registry=registry,
        )

    def handle_acquire(self, payload: AcquireEventPayload) -> None:
        """Handle an acquisition callback."""
        status = "hit" if payload.lease else "miss"
        labels = {
            "pool": payload.pool_name,
            "consumer": payload.consumer_name,
            "selector": payload.selector.value,
            "status": status,
        }
        self._acquire_total.labels(**labels).inc()
        self._acquire_duration_seconds.labels(**labels).observe(
            max(payload.duration_ms, 0) / 1000
        )
        self._set_pool_gauges(payload.pool_name, payload.pool_stats)

    def handle_release(self, payload: ReleaseEventPayload) -> None:
        """Handle a release callback."""
        pool_label = payload.pool_name or "unknown"
        self._release_total.labels(pool=pool_label).inc()
        lease_duration_ms = payload.lease_duration_ms or 0
        self._lease_duration_seconds.labels(pool=pool_label).observe(
            max(lease_duration_ms, 0) / 1000
        )
        self._set_pool_gauges(pool_label, payload.pool_stats)

    def _set_pool_gauges(
        self, pool_name: str, pool_stats: Optional[PoolStatsSnapshot]
    ) -> None:
        if pool_stats is None:
            return

        pool_label = pool_stats.pool_name or pool_name

        self._available_gauge.labels(pool=pool_label).set(
            pool_stats.available_proxies
        )
        self._active_gauge.labels(pool=pool_label).set(pool_stats.active_proxies)
        self._leased_gauge.labels(pool=pool_label).set(pool_stats.leased_proxies)


def register_prometheus_metrics(manager, **kwargs) -> PrometheusMetricsRecorder:
    """
    Register Prometheus metrics callbacks on a ProxyManager instance.

    Returns the recorder so callers can access the registry or customize
    histograms after registration.
    """
    from pharox.manager import ProxyManager

    if not isinstance(manager, ProxyManager):
        raise TypeError("manager must be a ProxyManager instance.")

    recorder = PrometheusMetricsRecorder(**kwargs)
    manager.register_acquire_callback(recorder.handle_acquire)
    manager.register_release_callback(recorder.handle_release)
    return recorder
