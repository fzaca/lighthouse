"""Public exports for the Pharox proxy management toolkit."""

from .async_helpers import (
    acquire_proxy_async,
    acquire_proxy_with_retry_async,
    release_proxy_async,
    with_lease_async,
    with_retrying_lease_async,
)
from .health import HealthChecker, HealthCheckOrchestrator
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
    SelectorStrategy,
)
from .storage import InMemoryStorage, IStorage
from .utils import (
    bootstrap_consumer,
    bootstrap_pool,
    bootstrap_proxy,
)

__all__ = [
    "Consumer",
    "HealthCheckOrchestrator",
    "HealthChecker",
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
    "acquire_proxy_async",
    "acquire_proxy_with_retry_async",
    "release_proxy_async",
    "with_lease_async",
    "with_retrying_lease_async",
    "bootstrap_consumer",
    "bootstrap_pool",
    "bootstrap_proxy",
]
