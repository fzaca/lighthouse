---
title: ProxyManager Reference
description: API reference and behavioural notes for pharox.manager.ProxyManager.
---
# `ProxyManager`

`ProxyManager` orchestrates leasing, releasing, and maintenance of proxies while
delegating persistence to an `IStorage` adapter.

```python
from pharox import ProxyManager
manager = ProxyManager(storage)
```

## Constructor

```python
ProxyManager(storage: IStorage)
```

- `storage`: Concrete implementation of `pharox.storage.IStorage`.
- The manager keeps no in-memory state besides registered callbacks.

## Core Methods

### `acquire_proxy`

```python
def acquire_proxy(
    pool_name: str,
    consumer_name: str | None = None,
    duration_seconds: int = 300,
    filters: ProxyFilters | None = None,
    selector: SelectorStrategy | None = None,
) -> Lease | None
```

- Validates `duration_seconds > 0`.
- Auto-registers the default consumer (`"default"`) using
  `storage.ensure_consumer`.
- Calls `storage.cleanup_expired_leases()` before searching for a proxy.
- Uses `storage.find_available_proxy` + `storage.create_lease`.
- Returns `None` when no eligible proxy exists.
- Accepts an optional `selector` hint (`SelectorStrategy`) to influence the order
  in which adapters return proxies. Defaults to first-available if omitted.

### `release_proxy`

```python
def release_proxy(lease: Lease) -> None
```

- Delegates to `storage.release_lease`.
- Triggers release callbacks after storage completes.

### `cleanup_expired_leases`

```python
def cleanup_expired_leases() -> int
```

- Pass-through to `storage.cleanup_expired_leases`.
- Returns number of leases released.

### `with_lease`

```python
@contextmanager
def with_lease(
    pool_name: str,
    consumer_name: str | None = None,
    duration_seconds: int = 300,
    filters: ProxyFilters | None = None,
    selector: SelectorStrategy | None = None,
) -> Iterator[Lease | None]
```

- Wraps `acquire_proxy` and guarantees `release_proxy` in a `finally` block.
- Yields `None` when acquisition fails so callers can retry gracefully.

### Selector Strategies

`SelectorStrategy` enumerates the available selection behaviours:

- `FIRST_AVAILABLE` (default): deterministic first-fit ordered by `checked_at`
  descending, then `proxy.id`.
- `LEAST_USED`: prioritises proxies with the fewest active leases, tying by
  `checked_at` and `proxy.id`.
- `ROUND_ROBIN`: cycles through the pool in a deterministic order backed by
  storage so concurrent workers share proxies fairly.

All adapters must support `FIRST_AVAILABLE`; reference adapters (in-memory and
PostgreSQL) also implement the other strategies. Custom adapters can choose to
ignore optional strategies, but should document the behaviour for callers.

## Callback Registration

```python
from pharox import (
    AcquireEventPayload,
    ReleaseEventPayload,
)

manager.register_acquire_callback(Callable[[AcquireEventPayload], None])
manager.register_release_callback(Callable[[ReleaseEventPayload], None])
```

- `AcquireEventPayload` includes the resulting `Lease` (or `None`), the pool and
  consumer names, resolved filters, the selected `SelectorStrategy`,
  `started_at` / `completed_at` timestamps, the execution duration in
  milliseconds, and a `PoolStatsSnapshot`.
- `ReleaseEventPayload` contains the released `Lease`, `released_at`, computed
  lease duration, and the same pool stats snapshot captured after the release.
- Callbacks run synchronously; keep them lightweight or hand off to background
  workers.

### `PoolStatsSnapshot`

`PoolStatsSnapshot` reports aggregated counts per pool:

- `total_proxies`, `active_proxies`, `available_proxies`
- `leased_proxies` (proxies with at least one active lease)
- `total_leases` (sum of `current_leases` across the pool)
- `collected_at` timestamp for when the snapshot was generated

## Async Helpers

The core manager is synchronous, but Pharox exposes thin wrappers to make it
ergonomic in `asyncio` applications:

```python
from pharox import (
    acquire_proxy_async,
    release_proxy_async,
    with_lease_async,
)
```

- `acquire_proxy_async` and `release_proxy_async` delegate to the synchronous
  manager via `asyncio.to_thread`, keeping event loops responsive.
- `with_lease_async` mirrors the synchronous context manager while ensuring
  leases are released when the async block exits—even if an exception occurs.

Use these helpers whenever your storage adapter is synchronous but the calling
code runs inside an async worker or FastAPI route handler.

## Default Consumer Name

- `ProxyManager.DEFAULT_CONSUMER_NAME == "default"`.
- Auto-created on first acquisition without an explicit `consumer_name`.

## Best Practices

- Register callbacks once at process startup to avoid duplicate telemetry.
- Combine `with_lease` with `try/except` if you need custom error handling.
- Schedule `cleanup_expired_leases` periodically for long-running services.
- Use `ProxyFilters` to offload selection logic to storage adapters.
