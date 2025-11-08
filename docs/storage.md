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

## Planning Additional Adapters

Future storage modules might target:

- **Relational databases** (PostgreSQL, MySQL) using SQLAlchemy or async drivers.
- **Document stores** (MongoDB) for flexible metadata.
- **Distributed caches** (Redis) when leases need to be tracked at high volume.

Keep the adapter project-specific so the toolkit remains storage-agnostic. When
multiple teams need the same adapter, consider publishing it as a separate
package that depends on `pharox`.
