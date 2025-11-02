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
) -> Lease | None
```

- Validates `duration_seconds > 0`.
- Auto-registers the default consumer (`"default"`) using
  `storage.ensure_consumer`.
- Calls `storage.cleanup_expired_leases()` before searching for a proxy.
- Uses `storage.find_available_proxy` + `storage.create_lease`.
- Returns `None` when no eligible proxy exists.

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
) -> Iterator[Lease | None]
```

- Wraps `acquire_proxy` and guarantees `release_proxy` in a `finally` block.
- Yields `None` when acquisition fails so callers can retry gracefully.

## Callback Registration

```python
manager.register_acquire_callback(
    Callable[[Lease | None, str, str, ProxyFilters | None], None]
)
manager.register_release_callback(Callable[[Lease], None])
```

- Acquire callbacks run after each `acquire_proxy` attempt. Receive `(lease,
  pool_name, consumer_name, filters)`.
- Release callbacks run only when a lease is successfully released.
- Callbacks run synchronously; keep them lightweight or hand off to background
  workers.

## Default Consumer Name

- `ProxyManager.DEFAULT_CONSUMER_NAME == "default"`.
- Auto-created on first acquisition without an explicit `consumer_name`.

## Best Practices

- Register callbacks once at process startup to avoid duplicate telemetry.
- Combine `with_lease` with `try/except` if you need custom error handling.
- Schedule `cleanup_expired_leases` periodically for long-running services.
- Use `ProxyFilters` to offload selection logic to storage adapters.
