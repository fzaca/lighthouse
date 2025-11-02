---
title: Bootstrap Helpers Reference
description: Reference for the bootstrap utilities that seed storage during tests, demos, and scripts.
---
# Bootstrap Helpers

The `pharox.utils.bootstrap` module provides convenience functions that seed
storage adapters with consumers, pools, and proxies. They are optional but help
reduce boilerplate in tests, documentation, and quick demos.

```python
from pharox import bootstrap_consumer, bootstrap_pool, bootstrap_proxy
```

## `bootstrap_consumer`

```python
def bootstrap_consumer(
    storage: IStorage,
    *,
    name: str = "default-consumer",
    consumer_id: UUID | None = None,
) -> Consumer
```

- Adds a `Consumer` to storage using `storage.add_consumer` when available.
- Falls back to `storage.ensure_consumer`, returning a `Consumer` with the UUID
  from the adapter.
- Useful for seeding named tenants during tests.

## `bootstrap_pool`

```python
def bootstrap_pool(
    storage: IStorage,
    *,
    name: str = "default-pool",
    description: str | None = None,
    pool_id: UUID | None = None,
) -> ProxyPool
```

- Requires the storage adapter to expose `add_pool`.
- Returns the stored `ProxyPool`.
- Raise an `AttributeError` when the adapter cannot add pools directly—ideal for
  catching unsupported helpers in production adapters.

## `bootstrap_proxy`

```python
def bootstrap_proxy(
    storage: IStorage,
    *,
    pool: ProxyPool,
    host: str,
    port: int,
    protocol: ProxyProtocol = ProxyProtocol.HTTP,
    status: ProxyStatus = ProxyStatus.ACTIVE,
    proxy_id: UUID | None = None,
    **extra_fields: Any,
) -> Proxy
```

- Expects `storage.add_proxy` to be available.
- Returns the stored `Proxy`; if the adapter implements `get_proxy_by_id`, the
  helper fetches the persisted copy to capture computed fields (e.g., defaults).
- Accepts additional keyword arguments to populate provider metadata, auth
  credentials, or geospatial data.

## When to Use Them

| Context | Recommendation |
| --- | --- |
| Unit tests | Seed fixtures quickly without writing adapter-specific code. |
| Tutorials & notebooks | Keep focus on orchestration logic, not boilerplate. |
| Production bootstrap | Implement environment-specific scripts instead of using these helpers directly. |

## Related Topics

- [Quickstart](../getting-started/quickstart.md)
- [Embed Pharox in a Worker](../how-to/embed-worker.md)
- [`ProxyManager` reference](proxy-manager.md)
