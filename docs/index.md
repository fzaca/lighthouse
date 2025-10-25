# Lighthouse Toolkit

Welcome to the documentation hub for the Lighthouse proxy-management toolkit.
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
  Lighthouse component.

## Quickstart

Install the package from PyPI and wire the in-memory storage to experiment
locally:

```bash
pip install lighthouse
```

```python
from lighthouse import (
    Consumer,
    InMemoryStorage,
    Proxy,
    ProxyManager,
    ProxyPool,
    ProxyStatus,
)

storage = InMemoryStorage()
manager = ProxyManager(storage=storage)

# Seed a default consumer and pool
consumer = Consumer(name=manager.DEFAULT_CONSUMER_NAME)
storage.add_consumer(consumer)
pool = ProxyPool(name="latam-residential")
storage.add_pool(pool)

storage.add_proxy(
    Proxy(
        host="1.1.1.1",
        port=8080,
        protocol="http",
        pool_id=pool.id,
        status=ProxyStatus.ACTIVE,
    )
)

lease = manager.acquire_proxy(pool_name=pool.name)
if lease:
    print("Proxy leased!", lease.proxy_id)
    manager.release_proxy(lease)
```

For more advanced examples and real-host testing, explore the draft script in
`drafts/run_proxy_health_checks.py`.

## Ecosystem at a Glance

The toolkit is the shared engine used by every entry point:

- **SDK:** Ships the same models for automation scripts and workers while
  speaking to the FastAPI service when shared state is needed.
- **Service:** Composes the toolkit with production storage, authentication, and
  orchestration concerns.
- **Frontend:** Talks to the service; never to the toolkit directly.

The separation keeps the toolkit stateless and reusable while letting the
service own multi-tenancy, scheduling, and auditing logic.

## Where to Go Next

- Understand leasing flows in the [Proxy Manager guide](proxy-manager.md).
- Review available models and filters in [Models & Filters](models.md).
- Explore the configurable [Health Checks](health-checks.md).
- Learn how to plug your database in [Storage Adapters](storage.md).
- Visit the GitHub repository for issue tracking and release notes:
  <https://github.com/fzaca/lighthouse>.
