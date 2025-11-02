# Proxy Manager

`ProxyManager` is the high-level orchestration API for leasing and releasing
proxies. It uses a storage backend that implements the `IStorage` interface to
keep track of pools, proxies, consumers, and leases.

## Creating a Manager

```python
from pharox import InMemoryStorage, ProxyManager

storage = InMemoryStorage()
manager = ProxyManager(storage)
```

The manager itself is stateless; all persistent data lives in the storage
backend. You can use the bundled in-memory adapter for tests and scripts, or
wire your own adapter for production.

## Leasing a Proxy

```python
lease = manager.acquire_proxy(
    pool_name="latam-residential",
    consumer_name="worker-1",
    duration_seconds=300,
)

if lease:
    print("Leased proxy", lease.proxy_id)
else:
    print("No proxy available")
```

Key points:

- If `consumer_name` is omitted, the manager falls back to the default consumer
  (`ProxyManager.DEFAULT_CONSUMER_NAME`). Make sure that consumer exists in
  storage.
- `duration_seconds` defines when the lease expires. The storage adapter is
  responsible for releasing expired leases.
- The manager automatically calls `cleanup_expired_leases()` before trying to
  allocate a proxy, so stale leases do not block new requests.

## Releasing a Proxy

```python
if lease:
    manager.release_proxy(lease)
```

Leases should be released as soon as the caller finishes using the proxy. The
storage layer decrements `current_leases` and updates the lease status.

## Using the `with_lease` Context Manager

To avoid manual `try/finally` blocks, `ProxyManager` exposes a context manager
that automatically releases the lease when the block exits:

```python
with manager.with_lease(
    pool_name="latam-residential",
    consumer_name="worker-1",
    duration_seconds=120,
) as lease:
    if not lease:
        raise RuntimeError("No proxy available")

    proxy = storage.get_proxy_by_id(lease.proxy_id)
    do_work(proxy)
```

If acquisition fails, the context yields `None` so your code can decide whether
to retry or fall back to another pool. When a lease is returned, the manager
releases it even if exceptions occur inside the `with` block.

## Filtering Proxies

Use `ProxyFilters` to target specific proxies. Filters apply metadata such as
country, provider, or geolocation:

```python
from pharox import ProxyFilters

filters = ProxyFilters(country="AR", source="oxylabs")
lease = manager.acquire_proxy(
    pool_name="latam-residential",
    consumer_name="worker-1",
    filters=filters,
)
```

If you need radius-based matching, include `latitude`, `longitude`, and
`radius_km`. Storage adapters are in charge of interpreting these filters.

## Handling Concurrency Limits

Each `Proxy` can define `max_concurrency`. The storage implementation checks the
current lease count and prevents over-leasing.

```python
from pharox import Proxy, ProxyStatus

proxy = Proxy(
    host="1.1.1.1",
    port=8080,
    protocol="http",
    pool_id=pool.id,
    status=ProxyStatus.ACTIVE,
    max_concurrency=2,
)
```

If all slots are in use, `acquire_proxy` returns `None` and the caller can retry
or pick another pool.

## Cleaning Up Expired Leases

You can trigger cleanup manually when running background jobs:

```python
released = manager.cleanup_expired_leases()
print("Expired leases released:", released)
```

Well-behaved storage adapters should also perform cleanup on their own cadence
(e.g., cron job, background task, or database job).

## Lifecycle Callbacks

Register callbacks to hook into acquisition and release events—for example, to
emit metrics or structured logs:

```python
def on_acquire(lease, pool, consumer, filters):
    if lease:
        print(f"{consumer} acquired {lease.proxy_id} from {pool}")
    else:
        print(f"{consumer} failed to acquire a proxy from {pool}")

def on_release(lease):
    print(f"Released {lease.proxy_id}")

manager.register_acquire_callback(on_acquire)
manager.register_release_callback(on_release)
```

Callbacks always run after storage operations complete. The acquire hook receives
the resulting `Lease` (or `None`), the pool name, consumer name, and filters used,
so you can record failure rates or latency per pool. The release hook only
triggers when a lease is successfully released.
