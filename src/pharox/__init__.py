"""Public exports for the Pharox proxy management toolkit."""

from .async_helpers import (
    acquire_proxy_async,
    acquire_proxy_with_retry_async,
    release_proxy_async,
    with_lease_async,
    with_retrying_lease_async,
)
from .benchmarks import (
    BenchmarkResult,
    run_health_benchmark,
    run_leasing_benchmark,
)
from .exceptions import (
    ConsumerNotFoundError,
    InvalidLeaseError,
    PharoxError,
    PoolNotFoundError,
    ProxyNotFoundError,
    ProxyUnavailableError,
)
from .health import HealthChecker, HealthCheckOrchestrator, HealthCheckStrategy
from .manager import ProxyManager
from .models import (
    AcquireEventPayload,
    Consumer,
    HealthCheckOptions,
    HealthCheckResult,
    Lease,
    LeaseStatus,
    PoolStatsSnapshot,
    Proxy,
    ProxyCredentials,
    ProxyFilters,
    ProxyPool,
    ProxyProtocol,
    ProxyStatus,
    ReleaseEventPayload,
    RetryConfig,
    SelectorStrategy,
)
from .observability import (
    DEFAULT_LATENCY_BUCKETS,
    DEFAULT_QUANTILES,
    PrometheusMetricsRecorder,
    StructuredLogger,
    register_prometheus_metrics,
)
from .storage import InMemoryStorage, IStorage
from .utils import (
    bootstrap_consumer,
    bootstrap_pool,
    bootstrap_proxy,
)

__all__ = [
    "ConsumerNotFoundError",
    "InvalidLeaseError",
    "PharoxError",
    "PoolNotFoundError",
    "ProxyNotFoundError",
    "ProxyUnavailableError",
    "Consumer",
    "HealthCheckOrchestrator",
    "HealthChecker",
    "HealthCheckStrategy",
    "HealthCheckOptions",
    "HealthCheckResult",
    "IStorage",
    "InMemoryStorage",
    "Lease",
    "LeaseStatus",
    "Proxy",
    "ProxyCredentials",
    "ProxyFilters",
    "ProxyManager",
    "ProxyPool",
    "ProxyProtocol",
    "ProxyStatus",
    "PoolStatsSnapshot",
    "SelectorStrategy",
    "AcquireEventPayload",
    "ReleaseEventPayload",
    "RetryConfig",
    "acquire_proxy_async",
    "acquire_proxy_with_retry_async",
    "release_proxy_async",
    "with_lease_async",
    "with_retrying_lease_async",
    "bootstrap_consumer",
    "bootstrap_pool",
    "bootstrap_proxy",
    "BenchmarkResult",
    "run_health_benchmark",
    "run_leasing_benchmark",
    "PrometheusMetricsRecorder",
    "StructuredLogger",
    "register_prometheus_metrics",
    "DEFAULT_LATENCY_BUCKETS",
    "DEFAULT_QUANTILES",
]
