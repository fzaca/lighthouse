# Storage Adapters

The toolkit separates business rules from persistence using the `IStorage`
interface. You can plug in custom adapters for your database while reusing the
same acquisition logic across applications.

## In-Memory Storage

The bundled `InMemoryStorage` is ideal for tests and exploratory scripts.

```python
from lighthouse import (
    Consumer,
    InMemoryStorage,
    Proxy,
    ProxyPool,
    ProxyStatus,
)

storage = InMemoryStorage()

pool = ProxyPool(name="latam-residential")
storage.add_pool(pool)

storage.add_consumer(Consumer(name="default"))

storage.add_proxy(
    Proxy(
        host="186.33.123.10",
        port=8080,
        protocol="http",
        pool_id=pool.id,
        status=ProxyStatus.ACTIVE,
    )
)
```

Characteristics:

- Thread-safe through an internal `RLock`.
- Keeps data structures in Python dictionaries; nothing is persisted to disk.
- Provides helper methods (`add_pool`, `add_proxy`, `add_consumer`) to seed test
  data. Production adapters can expose similar helpers or rely on migrations.
- `ProxyManager` automatically calls `ensure_consumer` for the default consumer
  so first acquisitions can succeed without manual seeding.

## Implementing `IStorage`

Custom adapters live in your service or SDK codebase. They must implement:

- `find_available_proxy(pool_name, filters)`
- `create_lease(proxy, consumer_name, duration_seconds)`
- `ensure_consumer(consumer_name)`
- `release_lease(lease)`
- `cleanup_expired_leases()`

Typical responsibilities include:

1. Translating `ProxyFilters` into database queries.
2. Enforcing `max_concurrency` when creating leases.
3. Persisting lease state changes and adjusting `current_leases` counters.
4. Returning defensive copies of models so callers cannot mutate shared state.

You can extend the models with extra fields (e.g., `tags`, `datacenter`) as long
as they round-trip through the adapter and the additional metadata remains
optional for other consumers.

## Planning Additional Adapters

Future storage modules might target:

- **Relational databases** (PostgreSQL, MySQL) using SQLAlchemy or async drivers.
- **Document stores** (MongoDB) for flexible metadata.
- **Distributed caches** (Redis) when leases need to be tracked at high volume.

Keep the adapter project-specific so the toolkit remains storage-agnostic. When
multiple teams need the same adapter, consider publishing it as a separate
package that depends on `lighthouse`.
