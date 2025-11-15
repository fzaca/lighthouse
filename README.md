# Pharox Core

[![Python Versions](https://img.shields.io/pypi/pyversions/pharox.svg)](https://pypi.org/project/pharox/)
[![PyPI Version](https://img.shields.io/pypi/v/pharox.svg)](https://pypi.org/project/pharox/)
[![CI Status](https://github.com/fzaca/pharox/actions/workflows/test.yml/badge.svg)](https://github.com/fzaca/pharox/actions/workflows/test.yml)
[![License](https://img.shields.io/pypi/l/pharox.svg)](https://github.com/fzaca/pharox/blob/main/LICENSE)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Docs](https://img.shields.io/badge/docs-shadcn-blue?logo=mkdocs&logoColor=white)](https://fzaca.github.io/pharox/)

The foundational Python toolkit for building robust proxy management systems.

`pharox` provides pure, domain-agnostic business logic for managing the
entire lifecycle of network proxies. The library is designed as a reusable
dependency for any Python application that needs to acquire, lease, and monitor
proxies without inheriting opinionated service architecture.

- 📚 Documentation: <https://fzaca.github.io/pharox/>

---

## Key Features

*   **Proxy Leasing System:** A powerful system to "lease" proxies to consumers, with support for exclusive, shared (concurrent), and unlimited usage.
*   **Pluggable Storage:** A clean interface (`IStorage`) that decouples the core logic from the database, allowing you to "plug in" any storage backend (e.g., in-memory, PostgreSQL, MongoDB).
*   **Health Checking Toolkit:** A protocol-aware `HealthChecker` with configurable options for HTTP, HTTPS, and SOCKS proxies.
*   **Modern & Type-Safe:** Built with Python 3.10+, Pydantic v2, and a 100% type-annotated codebase.
*   **Toolkit, Not a Framework:** Provides focused utilities that can be embedded inside your own scripts, workers, or services without imposing a runtime.

## Installation

You can install `pharox` directly from PyPI:

```bash
pip install pharox
```

Need the SQL adapter tooling? Install the optional extras:

```bash
pip install 'pharox[postgres]'
# or, if you're hacking on the repo:
poetry install --extras postgres
```

## Quickstart Example

Here is a simple example of how to use `pharox` with the default `InMemoryStorage` to acquire and release a proxy.

```python
from pharox import (
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

# The manager uses a "default" consumer if none is specified and will
# auto-register it in the storage when first needed.

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

If your worker needs to wait for capacity, call
`manager.acquire_proxy_with_retry(...)` (or the `manager.with_retrying_lease`
context manager) to add exponential backoff without scattering custom loops
throughout your codebase.

### Filtering and Geospatial Matching

`ProxyFilters` let you target proxies by provider metadata or geographic
proximity. The storage layer handles the matching logic, including radius-based
searches using latitude and longitude.

```python
from pharox import ProxyFilters

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

### Health Checks Across Protocols

Use `HealthChecker` to verify connectivity through HTTP, HTTPS, or SOCKS proxies.
Health checks are configurable via `HealthCheckOptions`, letting you define
target URLs, expected status codes, retry counts, and latency thresholds.

```python
from pharox import HealthCheckOptions, HealthChecker, ProxyStatus

checker = HealthChecker()
options = HealthCheckOptions(
    target_url="https://example.com/status/204",
    expected_status_codes=[204],
    attempts=2,
    slow_threshold_ms=1500,
)

proxy = storage.get_proxy_by_id(lease.proxy_id)
health = await checker.check_proxy(proxy, options=options)

if health.status in {ProxyStatus.ACTIVE, ProxyStatus.SLOW}:
    print("Proxy ready for workloads")
else:
    print(f"Proxy inactive: {health.error_message}")
```

## Embedding the Toolkit

`pharox` is intentionally agnostic about where it runs. Typical usage
includes:

* **Automation scripts and workers** leasing proxies with `ProxyManager` and
  performing health probes before dispatching workloads.
* **Custom services** that provide APIs or dashboards on top of the toolkit by
  implementing the `IStorage` contract for their own databases.
* **Standalone applications** that rely on the in-memory storage adapter for
  quick tasks or testing harnesses.

The in-memory adapter included with the package is great for development. For
production, implement `IStorage` to connect the toolkit to your own persistence
layer.

## Examples

- `pharox.storage.postgres.PostgresStorage` provides the reference PostgreSQL
  adapter. The accompanying `examples/postgres/` directory bundles Docker
  Compose, schema migrations, and customization notes you can copy into your
  services.

## PostgreSQL Adapter Quickstart

Pharox bundles a production-ready SQL adapter so you can persist pools, proxies,
and leases without building storage plumbing from scratch.

1. **Install the extras**

   ```bash
   pip install 'pharox[postgres]'
   # or
   poetry install --extras postgres
   ```

2. **Bring up Postgres locally**

   ```bash
   docker compose -f examples/postgres/docker-compose.yml up -d
   psql postgresql://pharox:pharox@localhost:5439/pharox \
       -f examples/postgres/migrations/0001_init.sql
   psql postgresql://pharox:pharox@localhost:5439/pharox \
       -f examples/postgres/migrations/0002_selector_state.sql
   ```

3. **Use the adapter in code**

   ```python
   from sqlalchemy import create_engine

   from pharox.manager import ProxyManager
   from pharox import SelectorStrategy
   from pharox.storage.postgres import PostgresStorage

   engine = create_engine("postgresql+psycopg://pharox:pharox@localhost:5439/pharox")
   storage = PostgresStorage(engine=engine)
   manager = ProxyManager(storage=storage)
   lease = manager.acquire_proxy(
       pool_name="latam-residential",
       consumer_name="worker-1",
       selector=SelectorStrategy.LEAST_USED,
   )
   if lease:
       print("Got proxy", lease.proxy_id)
   ```

4. **Run the storage contract suite (optional)**

   ```bash
   PHAROX_TEST_POSTGRES_URL=postgresql+psycopg://pharox:pharox@localhost:5439/pharox \
       poetry run pytest tests/test_storage_contract_postgres.py
   ```

Need more guidance? See the [Postgres adapter walkthrough](https://fzaca.github.io/pharox/how-to/postgres-adapter/)
and the [storage adapter cookbook](https://fzaca.github.io/pharox/storage/).

## Contributing

Contributions are welcome! Please see the `CONTRIBUTING.md` file for details on how to set up your development environment, run tests, and submit a pull request.

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.
