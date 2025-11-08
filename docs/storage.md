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

- `find_available_proxy(pool_name, filters)`
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
5. Returning defensive copies of models so callers cannot mutate shared state.

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

## Storage Adapter Cookbook

The checklist below distils recurring patterns from production adapters. Mix and
match the recipes according to your datastore.

### 1. Schema Checklist

Every adapter needs four core entities:

1. **Pools** – unique `name`, human-readable description, created timestamp.
2. **Consumers** – unique `name` so lease history can be traced.
3. **Proxies** – host/port/protocol, `status`, `max_concurrency`,
   `current_leases`, geo metadata (`country`, `city`, `latitude`, `longitude`),
   optional credentials, and timestamps (`checked_at`, `created_at`).
4. **Leases** – `proxy_id`, `pool_id`, `consumer_id`, current `status`,
   `acquired_at`, `expires_at`, `released_at`.

Keep IDs immutable (`UUID` or numeric) and guard relationships with foreign
keys. Add indexes on `proxy.pool_id`, `(pool_id, status)`, and any filterable
columns (`country`, `source`, `asn`) to keep lookups fast.

### 2. Acquire & Lease Recipes

`find_available_proxy` should:

- Join proxies with pools and lock the selected row (e.g., `FOR UPDATE SKIP LOCKED`).
- Filter by `status == ACTIVE` and `current_leases < max_concurrency`.
- Order by freshness (`checked_at`), tie-break with `id` to guarantee deterministic results.
- Apply `ProxyFilters` directly in SQL (country/source/geo radius). Fall back to
  Python-side filters only when your datastore lacks the feature.

`create_lease` and `release_lease` must increment/decrement `current_leases`
within the same transaction as the lease write. Clamp counters at zero to avoid
underflow. When a proxy is no longer available between `find_available_proxy`
and `create_lease`, raise a retriable error so `ProxyManager` can select the
next candidate.

`cleanup_expired_leases` should lock the affected leases, update their status
to `RELEASED`, and batch `current_leases` decrements using counters grouped by
`proxy_id`. This prevents stampedes when many leases expire at once.

### 3. Health & Stats

- Use `apply_health_check_result` to keep `status`, `checked_at`, and latency
  columns consistent (see the best-practice list above).
- `get_pool_stats` is queried on every callback. Cache-friendly SQL (single `SELECT`
  with conditional aggregates) prevents throttling your database.
- When adding new health metadata (error streaks, ban reasons), update the
  adapter models and document the semantics so downstream dashboards stay aligned.

### 4. Local Dev Loop

| Task | Recommended Tooling |
| --- | --- |
| Spin up dependencies | `docker compose -f examples/postgres/docker-compose.yml up -d` |
| Apply migrations | Plain SQL (`psql -f ...`) or Alembic, kept alongside the adapter |
| Seed data | CLI scripts (`drafts/`) or fixtures that call adapter helpers |
| Run contract suite | `poetry run pytest tests/test_storage_contract_<adapter>.py` with `PHAROX_TEST_POSTGRES_URL` set |

The contract suite (`pharox.tests.adapters.storage_contract_suite`) ensures your
adapter matches the behaviour of `InMemoryStorage`. Use it before running long
health sweeps or deploying new columns.

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

Future storage modules might target:

- **Relational databases** (PostgreSQL, MySQL) using SQLAlchemy or async drivers.
- **Document stores** (MongoDB) for flexible metadata.
- **Distributed caches** (Redis) when leases need to be tracked at high volume.

Keep the adapter project-specific so the toolkit remains storage-agnostic. When
multiple teams need the same adapter, consider publishing it as a separate
package that depends on `pharox`.
