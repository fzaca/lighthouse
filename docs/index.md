# Pharox Toolkit

Welcome to the documentation hub for the Pharox proxy-management toolkit.
This site focuses on the components you embed inside scripts, workers, or
services.

## What You Get

- **Proxy lifecycle management:** Acquire and release proxies with concurrency
  limits and lease tracking handled for you.
- **Flexible storage adapters:** Implement the `IStorage` interface to back the
  toolkit with any persistence layer (PostgreSQL, Redis, in-memory, etc.).
- **Health checking helpers:** Run protocol-aware connectivity probes that the
  SDK and FastAPI service can reuse.
- **Type-safe models:** Pydantic v2 models define the schema shared across every
  Pharox component.

## Quickstart

Install the package from PyPI and wire the in-memory storage to experiment
locally:

```bash
pip install pharox
```

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

# Bootstrap a pool and proxy; the manager auto-creates the default consumer.
pool = bootstrap_pool(storage, name="latam-residential")
bootstrap_proxy(
    storage,
    pool=pool,
    host="1.1.1.1",
    port=8080,
    protocol=ProxyProtocol.HTTP,
    status=ProxyStatus.ACTIVE,
)

lease = manager.acquire_proxy(pool_name=pool.name)
if lease:
    print("Proxy leased!", lease.proxy_id)
    manager.release_proxy(lease)
```

The manager falls back to a `default` consumer automatically, so you only need
to seed explicit consumers when you want per-tenant tracking.

For more advanced examples and real-host testing, explore the draft script in
`drafts/run_proxy_health_checks.py`.

## Where to Go Next

- Understand leasing flows in the [Proxy Manager guide](proxy-manager.md).
- Review available models and filters in [Models & Filters](models.md).
- Explore the configurable [Health Checks](health-checks.md).
- Learn how to plug your database in [Storage Adapters](storage.md).
- Visit the GitHub repository for issue tracking and release notes:
  <https://github.com/fzaca/pharox>.
