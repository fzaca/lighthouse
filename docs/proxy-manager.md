# Proxy Manager

`ProxyManager` is the high-level orchestration API for leasing and releasing
proxies. It uses a storage backend that implements the `IStorage` interface to
keep track of pools, proxies, consumers, and leases.

## Creating a Manager

```python
from pharox import InMemoryStorage, ProxyManager, SelectorStrategy

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
    selector=SelectorStrategy.LEAST_USED,
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
- Set `selector` to a `SelectorStrategy` value when you need least-used or
  round-robin behaviour; otherwise it defaults to first-available.

## Releasing a Proxy

```python
if lease:
    manager.release_proxy(lease)
```

Leases should be released as soon as the caller finishes using the proxy. The
storage layer decrements `current_leases` and updates the lease status.

## Using Selector Strategies

Pharox exposes multiple selection strategies so you can choose how proxies are
distributed within a pool:

- `SelectorStrategy.FIRST_AVAILABLE` (default) returns the most recently checked
  proxy that is still available.
- `SelectorStrategy.LEAST_USED` prioritises the proxy with the fewest active
  leases, which balances load across large pools.
- `SelectorStrategy.ROUND_ROBIN` cycles through proxies in a deterministic
  order. The state lives in the storage backend so multiple workers share
  proxies fairly.

Pass the desired strategy to `manager.acquire_proxy`, `with_lease`, or the async
helpers whenever you need behaviour other than first-fit.

## Using the `with_lease` Context Manager

To avoid manual `try/finally` blocks, `ProxyManager` exposes a context manager
that automatically releases the lease when the block exits:

```python
with manager.with_lease(
    pool_name="latam-residential",
    consumer_name="worker-1",
    duration_seconds=120,
    selector=SelectorStrategy.ROUND_ROBIN,
) as lease:
    if not lease:
        raise RuntimeError("No proxy available")

    proxy = storage.get_proxy_by_id(lease.proxy_id)
    do_work(proxy)
```

If acquisition fails, the context yields `None` so your code can decide whether
to retry or fall back to another pool. When a lease is returned, the manager
releases it even if exceptions occur inside the `with` block.

### Retrying Acquisition with Backoff

Bursting workloads often need to wait for capacity. Use
`ProxyManager.acquire_proxy_with_retry` (or the
`manager.with_retrying_lease` context manager) to add bounded backoff:

```python
lease = manager.acquire_proxy_with_retry(
    pool_name="latam-residential",
    consumer_name="worker-1",
    max_attempts=5,
    backoff_seconds=0.25,
    backoff_multiplier=2.0,
    max_backoff_seconds=2.0,
)

if not lease:
    raise TimeoutError("Pool exhausted after retries")
```

The helper retries acquisition up to `max_attempts` times, sleeping between
attempts with exponential backoff. Pass `max_backoff_seconds` to cap the delay,
or override `sleep_fn` in tests to avoid real waiting.

### Async Flows

The manager itself is synchronous, but you can still consume it from `async` code
by off-loading blocking calls to a worker thread. Pharox bundles helpers for
this exact use case:

```python
import asyncio
from pharox import (
    acquire_proxy_async,
    acquire_proxy_with_retry_async,
    release_proxy_async,
    with_lease_async,
    with_retrying_lease_async,
)

async def runner(manager):
    lease = await acquire_proxy_async(
        manager,
        pool_name="latam-residential",
        consumer_name="worker-1",
    )
    if lease:
        await release_proxy_async(manager, lease)

async def main(manager):
    async with with_lease_async(
        manager,
        pool_name="latam-residential",
    ) as lease:
        if not lease:
            return
        # perform async work here

asyncio.run(main(manager))
```

All three helpers use `asyncio.to_thread` so they remain compatible with any
existing `IStorage` implementation without introducing a hard dependency on an
async driver. Need retries from async code? Swap in
`acquire_proxy_with_retry_async` or `with_retrying_lease_async` for the same API.

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

### Composite Filters and Predicates

`ProxyFilters` also support basic boolean logic:

- `all_of`: every nested clause must match.
- `any_of`: at least one nested clause must match.
- `none_of`: no nested clause may match.
- `predicate`: Python callable invoked with each candidate `Proxy`.

```python
filters = ProxyFilters(
    any_of=[
        ProxyFilters(country="AR", source="latam"),
        ProxyFilters(all_of=[ProxyFilters(country="BR"), ProxyFilters(source="andina")]),
    ],
    none_of=[ProxyFilters(city="blocked")],
    predicate=lambda proxy: proxy.port >= 8000,
)
```

Adapters evaluate the tree recursively. Predicates run in Python, so keep them
lightweight and deterministic; they are best suited for rule-like checks that
are awkward to express as equality filters.

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
from pharox import AcquireEventPayload, ReleaseEventPayload


def on_acquire(event: AcquireEventPayload):
    outcome = "acquired" if event.lease else "miss"
    duration = event.duration_ms
    stats = event.pool_stats.model_dump() if event.pool_stats else {}
    print(
        f"{event.consumer_name} {outcome} from {event.pool_name} "
        f"in {duration} ms — stats: {stats}"
        f" (selector={event.selector.value})"
    )


def on_release(event: ReleaseEventPayload):
    duration = event.lease_duration_ms or 0
    available = (
        event.pool_stats.available_proxies if event.pool_stats else "n/a"
    )
    print(
        f"Released {event.lease.proxy_id} after {duration} ms "
        f"(available proxies: {available})"
    )


manager.register_acquire_callback(on_acquire)
manager.register_release_callback(on_release)
```

Callbacks now receive structured payloads with high-resolution timestamps,
operation duration, and a `PoolStatsSnapshot`. Use these fields to emit metrics,
compute queueing time, or alert when pools trend toward exhaustion. The release
hook fires only when a lease is successfully released.
