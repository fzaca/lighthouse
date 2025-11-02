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

Lease a proxy from the pool. Prefer the context manager to guarantee cleanup,
even if the work inside the block raises an exception.

```python
with manager.with_lease(pool_name=pool.name) as lease:
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

## 5. Add Filters (Optional)

Target proxies by metadata or location using `ProxyFilters`.

```python
from pharox import ProxyFilters

filters = ProxyFilters(country="AR", source="oxylabs")
lease = manager.acquire_proxy(pool_name=pool.name, filters=filters)

if lease:
    print("Filtered lease:", lease.proxy_id)
    manager.release_proxy(lease)
```

## 6. Run a Health Check

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
- Learn how to [embed Pharox in a worker](../how-to/embed-worker.md) that runs
  inside a scheduler or automation pipeline.
- Explore the [PostgreSQL adapter guide](../how-to/postgres-adapter.md) to store
  leases and health metrics persistently.
