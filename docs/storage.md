# Storage Adapters

The toolkit separates business rules from persistence using the `IStorage`
interface. You can plug in custom adapters for your database while reusing the
same acquisition logic across applications.

!!! tip "Need a template?"
    Start from `examples/postgres/` (code, migrations, Docker) and follow the
    [PostgreSQL adapter walkthrough](how-to/postgres-adapter.md) to tailor it to
    your datastore.

## In-Memory Storage

The bundled `InMemoryStorage` is ideal for tests and exploratory scripts.

```python
from pharox import (
    InMemoryStorage,
    ProxyPool,
    ProxyProtocol,
    ProxyStatus,
    bootstrap_consumer,
    bootstrap_pool,
    bootstrap_proxy,
)

storage = InMemoryStorage()

bootstrap_consumer(storage, name="default")
pool = bootstrap_pool(storage, name="latam-residential")
bootstrap_proxy(
    storage,
    pool=pool,
    host="186.33.123.10",
    port=8080,
    protocol=ProxyProtocol.HTTP,
    status=ProxyStatus.ACTIVE,
)
```

Characteristics:

- Thread-safe through an internal `RLock`.
- Keeps data structures in Python dictionaries; nothing is persisted to disk.
- Provides helper methods (`add_pool`, `add_proxy`, `add_consumer`) to seed test
  data. Production adapters can expose similar helpers or rely on migrations.
- `ProxyManager` automatically calls `ensure_consumer` for the default consumer
  so first acquisitions can succeed without manual seeding. For custom
  consumers, the `bootstrap_consumer`, `bootstrap_pool`, and `bootstrap_proxy`
  helpers keep examples concise.

## Implementing `IStorage`

Custom adapters live in your service or SDK codebase. They must implement:

- `find_available_proxy(pool_name, filters, selector)`
- `create_lease(proxy, consumer_name, duration_seconds)`
- `ensure_consumer(consumer_name)`
- `release_lease(lease)`
- `cleanup_expired_leases()`
- `get_pool_stats(pool_name)`

Typical responsibilities include:

1. Translating `ProxyFilters` into database queries.
2. Enforcing `max_concurrency` when creating leases.
3. Persisting lease state changes and adjusting `current_leases` counters.
4. Computing pool snapshots for callbacks/telemetry (`PoolStatsSnapshot`).
5. Honouring selector hints, or clearly documenting unsupported strategies.
6. Returning defensive copies of models so callers cannot mutate shared state.

You can extend the models with extra fields (e.g., `tags`, `datacenter`) as long
as they round-trip through the adapter and the additional metadata remains
optional for other consumers.

### `apply_health_check_result` Best Practices

Adapters own the source of truth for proxy health. When implementing
`apply_health_check_result`, ensure the method:

- Updates `status` and `checked_at` atomically so new leases never see stale
  state. Use `SELECT ... FOR UPDATE` or equivalent row locks in SQL backends.
- Stores the latest latency/error metadata your organisation tracks (e.g.,
  round-trip time, HTTP code, failure reason) so future dashboards and hooks
  can consume it. Keep optional columns nullable for compatibility.
- Resets counters when a proxy recovers (e.g., clear `error_message`,
  decrement failure streaks) and consider pausing leases when repeated failures
  push the status to `INACTIVE` or `BANNED`.
- Ignores unknown proxies gracefully (return `None`) to keep orchestrators
  resilient if a row was removed mid-sweep.
- Emits updated `Proxy` copies (as the interface expects) so callbacks receive
  the latest snapshot without mutating shared state.

Document these behaviours in your adapter repo so operators know how health data
propagates into leasing decisions. See `examples/postgres/` for a concrete
reference.

## PostgreSQL Adapter

Pharox includes `pharox.storage.postgres.PostgresStorage`, a SQLAlchemy Core
adapter that implements every `IStorage` method.

### 1. Install the extra

```bash
pip install 'pharox[postgres]'
# or
poetry install --extras postgres
```

### 2. Provision PostgreSQL

```bash
docker compose -f examples/postgres/docker-compose.yml up -d
psql postgresql://pharox:pharox@localhost:5439/pharox \
    -f examples/postgres/migrations/0001_init.sql
psql postgresql://pharox:pharox@localhost:5439/pharox \
    -f examples/postgres/migrations/0002_selector_state.sql
psql postgresql://pharox:pharox@localhost:5439/pharox \
    -f examples/postgres/migrations/0002_selector_state.sql
```

Use the SQL migrations as a starting point, then migrate them into your own
Alembic/Flyway changelog before production. Migration `0002_selector_state.sql`
adds the `pool_selector_state` table that keeps round-robin cursors in sync
across workers—include it (or an equivalent structure) whenever you support
selector strategies.

### 3. Instantiate the adapter

```python
from sqlalchemy import create_engine

from pharox.manager import ProxyManager
from pharox.storage.postgres import PostgresStorage

engine = create_engine("postgresql+psycopg://pharox:pharox@localhost:5439/pharox")
storage = PostgresStorage(engine=engine)
manager = ProxyManager(storage=storage)
```

`PostgresStorage` exposes the same API surface as the in-memory adapter,
including filters, lease cleanup, pool stats, and `apply_health_check_result`.
Extend `pharox.storage.postgres.tables` if you need custom metadata columns.

### 4. Run the adapter contract suite

```bash
export PHAROX_TEST_POSTGRES_URL="postgresql+psycopg://pharox:pharox@localhost:5439/pharox"
poetry run pytest tests/test_storage_contract_postgres.py
```

The test truncates the tables between runs and verifies the adapter matches
the behaviour expected by `ProxyManager`.

### 5. Seed proxies for experiments

`drafts/run_postgres_health_checks.py` reseeds a pool with demo proxies and runs
health checks through the Postgres adapter. Update the host/port/credential
constants to point at your own providers when experimenting locally.

## Storage Adapter Cookbook

The checklist below distils recurring patterns from production adapters. Mix and
match the recipes according to your datastore.
*** End Patch

### 5. Observability Hooks

Expose acquisition/release telemetry via `ProxyManager` callbacks:

- Record miss rates (`lease is None`) to detect exhausted pools.
- Report `duration_ms` and `pool_stats.available_proxies` to your metrics stack.
- Log `lease_duration_ms` to spot jobs that hold proxies for too long.

See the [lifecycle hook guide](how-to/lifecycle-hooks.md) for code samples.

### Validate with Contract Tests

Use `pharox.tests.adapters.storage_contract_suite` to verify that your adapter
behaves like the in-memory reference. Provide fixtures that insert pools and
proxies into your datastore, then run the suite inside your `pytest` harness.
This catches subtle regressions (filters, concurrency, stats) before consumers
rely on the adapter in production.

!!! tip "Install extras"
    The optional `postgres` extra bundles SQLAlchemy, psycopg, and Alembic:
    `pip install 'pharox[postgres]'` or `poetry install --extras postgres`.

## Planning Additional Adapters

Pharox now ships a reference PostgreSQL adapter (`pharox.storage.postgres`) plus
examples/migrations under `examples/postgres/`. Future adapters might target:

- **Other relational databases** (MySQL, SQL Server) using SQLAlchemy or native drivers.
- **Document stores** (MongoDB) for flexible metadata.
- **Distributed caches** (Redis) when leases need to be tracked at high volume.

Keep each adapter project-specific so the toolkit remains storage-agnostic. When
multiple teams need the same implementation, consider publishing it as a
standalone package that depends on `pharox`.

## Using the Built-in PostgreSQL Adapter

Pharox includes `pharox.storage.postgres.PostgresStorage`, a SQLAlchemy Core
adapter that implements every `IStorage` method.

### 1. Install the extra

```bash
pip install 'pharox[postgres]'
# or
poetry install --extras postgres
```

### 2. Provision PostgreSQL

```bash
docker compose -f examples/postgres/docker-compose.yml up -d
psql postgresql://pharox:pharox@localhost:5439/pharox \
    -f examples/postgres/migrations/0001_init.sql
```

Use the SQL migrations as a starting point, then migrate them into your own
Alembic/Flyway changelog before production.

### 3. Instantiate the adapter

```python
from sqlalchemy import create_engine

from pharox.manager import ProxyManager
from pharox.storage.postgres import PostgresStorage

engine = create_engine("postgresql+psycopg://pharox:pharox@localhost:5439/pharox")
storage = PostgresStorage(engine=engine)
manager = ProxyManager(storage=storage)
```

`PostgresStorage` exposes the same API surface as the in-memory adapter,
including filters, lease cleanup, pool stats, and `apply_health_check_result`.
Extend `pharox.storage.postgres.tables` if you need custom metadata columns.

### 4. Run the adapter contract suite

```bash
export PHAROX_TEST_POSTGRES_URL="postgresql+psycopg://pharox:pharox@localhost:5439/pharox"
poetry run pytest tests/test_storage_contract_postgres.py
```

The test truncates the tables between runs and verifies the adapter matches
the behaviour expected by `ProxyManager`.

### 5. Seed proxies for experiments

`drafts/run_postgres_health_checks.py` reseeds a pool with demo proxies and runs
health checks through the Postgres adapter. Update the host/port/credential
constants to point at your own providers when experimenting locally.
