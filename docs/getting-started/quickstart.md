---
title: Pharox Quickstart
description: Install Pharox, bootstrap storage, lease proxies, and run a health check in under five minutes.
---
# Quickstart

This tutorial walks you through installing Pharox, seeding a proxy pool, leasing
a proxy, and releasing it safely. All code runs locally with the bundled
`InMemoryStorage`, so you do not need any external services.

## 1. Install Pharox

Create and activate a virtual environment (optional but recommended), then
install the package from PyPI:

```bash
pip install pharox
```

!!! info "Python version"
    Pharox targets Python 3.10+ and is fully type-hinted. If you are using pyenv
    or uv, make sure your interpreter is at least 3.10.

## 2. Bootstrap Storage and Manager

Initialize the storage adapter and `ProxyManager`. The manager is stateless and
delegates persistence to the storage backend.

```python
from pharox import (
    InMemoryStorage,
    ProxyManager,
    ProxyProtocol,
    ProxyStatus,
    SelectorStrategy,
    bootstrap_pool,
    bootstrap_proxy,
)

storage = InMemoryStorage()
manager = ProxyManager(storage=storage)
```

## 3. Seed a Pool and Proxy

Use the bootstrap helpers to register a pool and proxy. When no consumer name is
provided, the manager auto-registers the default consumer. The helper returns
the persisted `Proxy` so you can reuse it later in health checks.

```python
pool = bootstrap_pool(storage, name="latam-residential")
seed_proxy = bootstrap_proxy(
    storage,
    pool=pool,
    host="1.1.1.1",
    port=8080,
    protocol=ProxyProtocol.HTTP,
    status=ProxyStatus.ACTIVE,
)
```

## 4. Lease and Release a Proxy

Lease a proxy from the pool. Prefer `ProxyManager.with_lease`—the context
manager guarantees cleanup even if the work inside the block raises an
exception, and it accepts the same options as `acquire_proxy` (consumer name,
filters, custom durations, selector hints).

```python
with manager.with_lease(
    pool_name=pool.name,
    duration_seconds=60,
    selector=SelectorStrategy.FIRST_AVAILABLE,
) as lease:
    if not lease:
        raise RuntimeError("No proxy available")

    proxy = storage.get_proxy_by_id(lease.proxy_id)
    print("Leased proxy:", proxy.url)
    # Do useful work with the proxy here...
```

Behind the scenes Pharox:

1. Ensures the consumer exists in storage.
2. Cleans up expired leases to avoid blocking future acquisitions.
3. Finds and locks an eligible proxy.
4. Releases the lease automatically when the context closes.

Need to keep trying until capacity frees up? Replace the snippet with
`manager.with_retrying_lease(...)` (or call `manager.acquire_proxy_with_retry(...)`).
Both helpers add bounded exponential backoff before they give up, so you do not
have to hand-roll retry loops around every acquisition.

## 5. Emit Metrics via Callbacks

`ProxyManager` can publish acquisition/release events so you can tie into your
observability stack without forking the toolkit. Register callbacks once after
creating the manager (in the snippet below, `metrics_client` represents whatever
telemetry helper—StatsD, Prometheus, OTEL—you already use):

```python
from pharox import AcquireEventPayload, ReleaseEventPayload


def on_acquire(event: AcquireEventPayload):
    tags = {
        "pool": event.pool_name,
        "consumer": event.consumer_name,
        "selector": event.selector.value,
        "status": "hit" if event.lease else "miss",
    }
    duration = event.duration_ms or 0
    pool_stats = event.pool_stats.model_dump() if event.pool_stats else {}
    metrics_client.timing("pharox.acquire", duration, tags)
    metrics_client.gauge("pharox.pool.available", pool_stats.get("available_proxies", 0), tags)


def on_release(event: ReleaseEventPayload):
    duration = event.lease_duration_ms or 0
    tags = {"pool": event.lease.pool_name}
    metrics_client.timing("pharox.lease_duration", duration, tags)


manager.register_acquire_callback(on_acquire)
manager.register_release_callback(on_release)
```

The payloads include timestamps, pool stats, and latency numbers that map
directly to metrics or structured logs. Callbacks fire for **every** acquisition
attempt, including misses, so you can track saturation and alert early.

## 6. Add Filters (Optional)

Target proxies by metadata or location using `ProxyFilters`.

```python
from pharox import ProxyFilters

filters = ProxyFilters(country="AR", source="oxylabs")
lease = manager.acquire_proxy(pool_name=pool.name, filters=filters)

if lease:
    print("Filtered lease:", lease.proxy_id)
    manager.release_proxy(lease)
```

## 7. Choose a Selector (Optional)

Different workloads benefit from different proxy ordering. Use
`SelectorStrategy` to pick a strategy per acquisition:

```python
from pharox import SelectorStrategy

lease = manager.acquire_proxy(
    pool_name=pool.name,
    consumer_name="worker-1",
    selector=SelectorStrategy.LEAST_USED,
)
```

The in-memory and PostgreSQL adapters support:

- `FIRST_AVAILABLE` (default): deterministic first-fit.
- `LEAST_USED`: prioritises proxies with fewer active leases.
- `ROUND_ROBIN`: cycles through the pool fairly using storage-backed cursors.

## 8. Run a Health Check

Verify the proxy before using it in production. The health module classifies
results consistently across all Pharox integrations.

```python
import asyncio
from pharox import HealthCheckOptions, HealthChecker

checker = HealthChecker()
options = HealthCheckOptions(
    target_url="https://example.com/status/204",
    expected_status_codes=[204],
    attempts=2,
    timeout=5.0,
)

result = asyncio.run(checker.check_proxy(seed_proxy, options=options))
print(result.status, result.latency_ms)
```

!!! warning "SOCKS proxies"
    Install `httpx[socks]` alongside Pharox if you plan to probe SOCKS4/5
    proxies: `pip install "httpx[socks]"`.

## Next Steps

- Dive deeper into [`ProxyManager`](../reference/proxy-manager.md) and the
  lifecycle callbacks.
- Explore the [lifecycle hook recipes](../how-to/lifecycle-hooks.md) to wire
  metrics and logs without forking the toolkit.
- Learn how to [embed Pharox in a worker](../how-to/embed-worker.md) that runs
  inside a scheduler or automation pipeline.
- Explore the [PostgreSQL adapter guide](../how-to/postgres-adapter.md) to store
  leases and health metrics persistently.
