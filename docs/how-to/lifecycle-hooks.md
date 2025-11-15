---
title: Instrument Lifecycle Hooks
description: Capture ProxyManager acquisition/release events for metrics, logging, and alerts.
---
# Instrument Lifecycle Hooks

`ProxyManager` emits structured events every time it acquires or releases a
lease. This guide shows how to connect those callbacks to your observability
stack so you can track saturation, latency, and pool health without forking the
toolkit.

## 1. Know the Payloads

Callbacks receive Pydantic models that are already validated and timezone-aware:

| Field | AcquireEventPayload | ReleaseEventPayload | Notes |
| --- | --- | --- | --- |
| `lease` | `Lease \| None` | `Lease` | Acquisition payloads set `lease=None` when no proxy matched—log these misses to spot exhausted pools. |
| `pool_name` | `str` | `str \| None` | Release events carry the name stored on the lease. |
| `consumer_name` | `str` | — | Helps group metrics per worker/tenant. |
| `filters` | `ProxyFilters \| None` | — | Reuse filters inside logs to debug misconfigured selectors. |
| `selector` | `SelectorStrategy` | — | Strategy used when picking the proxy (first-available, least-used, round-robin). |
| `duration_ms` | `int` | — | How long the acquisition attempt took (including cleanup + storage calls). |
| `lease_duration_ms` | — | `int \| None` | Milliseconds between `acquired_at` and `released_at`. |
| `pool_stats` | `PoolStatsSnapshot \| None` | `PoolStatsSnapshot \| None` | Snapshot collected after the operation: totals, available proxies, leases in-flight. |

All timestamps (`started_at`, `completed_at`, `released_at`) live in UTC so they
can be compared safely across services.

## 2. Register Callbacks Once

Attach callbacks right after instantiating the manager (for example during app
startup or worker boot). Keep the functions fast—push heavy lifting to async
queues or background threads if needed.

```python
from pharox import AcquireEventPayload, ProxyManager, ReleaseEventPayload

manager = ProxyManager(storage=storage)


def on_acquire(event: AcquireEventPayload) -> None:
    ...


def on_release(event: ReleaseEventPayload) -> None:
    ...


manager.register_acquire_callback(on_acquire)
manager.register_release_callback(on_release)
```

Callbacks fire synchronously after each operation, so avoid blocking network
calls inline unless you control their latency.

## 3. Emit Metrics

Map the payload fields to timers and gauges in your telemetry stack. The example
below uses a hypothetical StatsD client, but any metrics backend works:

```python
def on_acquire(event: AcquireEventPayload) -> None:
    tags = {
        "pool": event.pool_name,
        "consumer": event.consumer_name,
        "selector": event.selector.value,
        "status": "hit" if event.lease else "miss",
    }
    metrics.timing("pharox.acquire.duration_ms", event.duration_ms, tags)
    available = (
        event.pool_stats.available_proxies if event.pool_stats else None
    )
    if available is not None:
        metrics.gauge("pharox.pool.available", available, tags)


def on_release(event: ReleaseEventPayload) -> None:
    tags = {"pool": event.pool_name or "unknown"}
    metrics.timing(
        "pharox.lease.duration_ms", event.lease_duration_ms or 0, tags
    )
```

Recommended metrics:

- Acquisition latency (bucketed histogram) grouped by pool/consumer.
- Miss rate (lease is `None`).
- Pool availability gauge (`available_proxies`, `active_proxies`, `total_leases`).
- Lease duration timers to detect stuck workloads.
- Per-selector breakdowns to verify that least-used and round-robin strategies
  distribute load as expected.

## 4. Log Structured Events

Structured logs make it easy to trace a proxy through your jobs. Include IDs,
filters, and pool stats so you can replay what happened during an incident.

```python
def on_acquire(event: AcquireEventPayload) -> None:
    logger.info(
        "pharox.acquire",
        extra={
            "pool": event.pool_name,
            "consumer": event.consumer_name,
            "duration_ms": event.duration_ms,
        "filters": event.filters.model_dump() if event.filters else None,
        "lease_id": event.lease.id if event.lease else None,
        "selector": event.selector.value,
        "available": event.pool_stats.available_proxies
            if event.pool_stats
            else None,
        },
    )
```

Log release events with the same correlation IDs (`lease.id`, `proxy_id`) so you
can tie acquisitions to completions.

## 5. Handle Misses and Errors

- Acquisitions run callbacks even when no proxy is available. Use this to alert
  when a pool approaches exhaustion or a selector filter is too strict.
- Release callbacks may run after retries or failures. Use `lease.released_at`
  to compute custom SLAs or decide when to quarantine a proxy.
- If a callback raises, it bubbles up to the caller. Wrap fragile telemetry code
  in `try/except` blocks so that logging outages do not block proxy leasing.

## 6. Test Your Hooks

In unit tests, register lightweight callbacks and capture the payloads in a
list. Use the in-memory storage adapter so tests run without external services:

```python
def test_acquire_callback_records_miss():
    storage = InMemoryStorage()
    manager = ProxyManager(storage=storage)
    events: list[AcquireEventPayload] = []
    manager.register_acquire_callback(events.append)

    lease = manager.acquire_proxy(pool_name="nope")
    assert lease is None

    assert len(events) == 1
    payload = events[0]
    assert payload.lease is None
    assert payload.pool_name == "nope"
```

Use similar assertions for release callbacks by seeding a proxy and calling
`manager.release_proxy`.

## Next Steps

- Revisit the [Proxy Manager deep dive](../proxy-manager.md) for more context on
  acquisition internals.
- Embed the manager in a worker using the
  [worker how-to](embed-worker.md) once your hooks are in place.
- Wire the payload data into your alerting stack to catch saturation before it
  impacts users.
