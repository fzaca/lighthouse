# Lighthouse Core

[![Python Versions](https://img.shields.io/pypi/pyversions/lighthouse.svg)](https://pypi.org/project/lighthouse/)
[![PyPI Version](https://img.shields.io/pypi/v/lighthouse.svg)](https://pypi.org/project/lighthouse/)
[![CI Status](https://github.com/fzaca/lighthouse/actions/workflows/test.yml/badge.svg)](https://github.com/fzaca/lighthouse/actions/workflows/test.yml)
[![License](https://img.shields.io/pypi/l/lighthouse.svg)](https://github.com/fzaca/lighthouse/blob/main/LICENSE)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

The foundational Python toolkit for building robust proxy management systems.

`lighthouse` provides the pure, domain-agnostic business logic for managing the entire lifecycle of network proxies. It is the engine that powers the Lighthouse ecosystem, designed to be used as a direct dependency in your Python applications.

---

## Key Features

*   **Proxy Leasing System:** A powerful system to "lease" proxies to consumers, with support for exclusive, shared (concurrent), and unlimited usage.
*   **Pluggable Storage:** A clean interface (`IStorage`) that decouples the core logic from the database, allowing you to "plug in" any storage backend (e.g., in-memory, PostgreSQL, MongoDB).
*   **Health Checking Toolkit:** A flexible, asynchronous utility (`AsyncHealthChecker`) to test proxy health, latency, and compatibility.
*   **Modern & Type-Safe:** Built with Python 3.10+, Pydantic v2, and a 100% type-annotated codebase.
*   **Toolkit, Not a Framework:** Provides focused utilities that can be embedded inside your own scripts, workers, or services without imposing a runtime.
*   **Ecosystem Ready:** Acts as the shared engine for the Lighthouse service and SDK so every entry point shares the same business rules.

## Installation

You can install `lighthouse` directly from PyPI:

```bash
pip install lighthouse
```

## Quickstart Example

Here is a simple example of how to use `lighthouse` with the default `InMemoryStorage` to acquire and release a proxy.

```python
from lighthouse import (
    Consumer,
    InMemoryStorage,
    Proxy,
    ProxyManager,
    ProxyPool,
    ProxyStatus,
)

# 1. Setup the storage and manager
storage = InMemoryStorage()
manager = ProxyManager(storage=storage)

# 2. Seed the storage with necessary data for the example
# In a real application, you would load this from your database.

# The manager uses a "default" consumer if none is specified,
# so we must add it to the storage for the example to work.
default_consumer = Consumer(name=manager.DEFAULT_CONSUMER_NAME)
storage.add_consumer(default_consumer)

# Create a pool and a proxy
pool = ProxyPool(name="latam-residential")
storage.add_pool(pool)

proxy = Proxy(
    host="1.1.1.1",
    port=8080,
    protocol="http",
    pool_id=pool.id,
    status=ProxyStatus.ACTIVE,
)
storage.add_proxy(proxy)

# 3. Acquire a proxy from the pool (without specifying a consumer)
print(f"Attempting to acquire a proxy from pool '{pool.name}'...")
lease = manager.acquire_proxy(pool_name=pool.name, duration_seconds=60)

if lease:
    leased_proxy = storage.get_proxy_by_id(lease.proxy_id)
    print(f"Success! Leased proxy: {leased_proxy.host}:{leased_proxy.port}")
    print(f"Lease acquired by consumer ID: {lease.consumer_id}")

    # ... do some work with the proxy ...

    # 4. Release the lease when done
    print("\nReleasing the lease...")
    manager.release_proxy(lease)
    print("Lease released.")

    proxy_after_release = storage.get_proxy_by_id(lease.proxy_id)
    print(f"Proxy lease count after release: {proxy_after_release.current_leases}")
else:
    print("Failed to acquire a proxy. None available.")
```

### Filtering and Geospatial Matching

`ProxyFilters` let you target proxies by provider metadata or geographic
proximity. The storage layer handles the matching logic, including radius-based
searches using latitude and longitude.

```python
from lighthouse import ProxyFilters

filters = ProxyFilters(
    country="AR",
    source="fast-provider",
    latitude=-34.6,
    longitude=-58.38,
    radius_km=50,
)

lease = manager.acquire_proxy(
    pool_name="latam-residential",
    consumer_name="team-madrid",
    filters=filters,
)

if lease:
    print("Got a proxy close to Buenos Aires!")
```

## The Lighthouse Ecosystem

`lighthouse` is the central engine of a larger ecosystem. The toolkit sits at the
core, and other projects compose it to support different user journeys:

*   **[lighthouse-sdk](https://github.com/fzaca/lighthouse-sdk):** Powers Python
    automation and workers. It reuses the toolkit models locally and can also
    call the service API when shared state is required.
*   **[lighthouse-service](https://github.com/fzaca/lighthouse-service):** A
    FastAPI application that exposes REST endpoints for browsers and external
    systems. The service delegates proxy lifecycle operations to the toolkit.
*   **[lighthouse-frontend](https://github.com/fzaca/lighthouse-frontend):** A
    web UI that interacts with the service layer.

Two main flows emerge:

1. **Automation:** End users run Python scripts or workers that depend on the
   SDK, which in turn leverages the toolkit directly and, when needed, talks to
   the FastAPI service for shared state.
2. **Web Experience:** End users access the web UI, which communicates with the
   FastAPI service. The service composes the toolkit with production storage and
   application concerns such as authentication.

The toolkit's storage adapters only handle proxy-related data (pools, proxies,
leases, consumers). User accounts, billing, and analytics live in the service or
in your own integrations. For a deeper explanation, see
[`docs/architecture.md`](docs/architecture.md).

## Contributing

Contributions are welcome! Please see the `CONTRIBUTING.md` file for details on how to set up your development environment, run tests, and submit a pull request.

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.
