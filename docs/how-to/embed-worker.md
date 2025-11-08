---
title: Embed Pharox in a Worker
description: Use ProxyManager and lifecycle callbacks inside a job or worker that executes scraping tasks.
---
# Embed Pharox in a Worker

This guide shows how to integrate Pharox into a long-running worker that leases
proxies, performs work, and emits observability events.

!!! example "Scenario"
    You operate a scraping worker scheduled by Celery or a cron job. Each job
    needs an exclusive proxy, must release it after use, and should record
    metrics about lease success/failure.

## 1. Set Up the Manager and Callbacks

Define callbacks once at process startup to centralise logging/metrics.

```python
import logging
from pharox import (
    AcquireEventPayload,
    InMemoryStorage,
    ProxyManager,
    ReleaseEventPayload,
)

logger = logging.getLogger("pharox.worker")

storage = InMemoryStorage()
manager = ProxyManager(storage=storage)

def on_acquire(event: AcquireEventPayload):
    outcome = "success" if event.lease else "failure"
    logger.info(
        "proxy.acquire",
        extra={
            "pool": event.pool_name,
            "consumer": event.consumer_name,
            "outcome": outcome,
            "duration_ms": event.duration_ms,
            "filters": event.filters.model_dump() if event.filters else None,
            "available": event.pool_stats.available_proxies
            if event.pool_stats
            else None,
        },
    )

def on_release(event: ReleaseEventPayload):
    logger.info(
        "proxy.release",
        extra={
            "proxy_id": event.lease.proxy_id,
            "lease_duration_ms": event.lease_duration_ms,
            "available": event.pool_stats.available_proxies
            if event.pool_stats
            else None,
        },
    )

manager.register_acquire_callback(on_acquire)
manager.register_release_callback(on_release)
```

!!! tip
    Swap `logging` for your telemetry stack (OpenTelemetry, StatsD, Prometheus)
    by pushing the same metadata to counters/histograms.

## 2. Write a Worker Function

Wrap the work in the `with_lease` context manager. Lease failures return `None`,
allowing you to requeue or back off gracefully.

```python
def process_account(account_id: str) -> None:
    with manager.with_lease(pool_name="residential", consumer_name="worker") as lease:
        if not lease:
            logger.warning("No proxy available; retrying account %s", account_id)
            raise RuntimeError("proxy unavailable")

        proxy = storage.get_proxy_by_id(lease.proxy_id)
        run_job(account_id, proxy.url)
```

Use your orchestration tool (Celery, RQ, APScheduler) to call `process_account`
with retry policies that fit your workload.

## 3. Handle Errors Safely

Because the context manager releases the lease in a `finally` block, any raised
exceptions do not leak the proxy. If you need custom recovery logic, use a
`try/except` inside the context:

```python
with manager.with_lease(pool_name="residential") as lease:
    if not lease:
        return
    try:
        run_job(...)
    except ProviderTimeout as exc:
        logger.exception("Work failed, marking proxy as suspect", exc_info=exc)
        # Optionally adjust proxy state in storage here.
```

## 4. Periodic Cleanup and Health Checks

Schedule a background job that releases expired leases and runs health sweeps:

```python
import asyncio
from pharox import HealthCheckOrchestrator

checker = HealthCheckOrchestrator(storage=storage)

async def sweep_proxies():
    proxies = storage.list_proxies(status="active")
    async for result in checker.stream_health_checks(proxies):
        logger.info(
            "proxy.health",
            extra={
                "proxy_id": result.proxy_id,
                "status": result.status.value,
                "latency_ms": result.latency_ms,
            },
        )

def nightly_maintenance():
    released = manager.cleanup_expired_leases()
    logger.info("Expired leases cleaned", extra={"released": released})
    asyncio.run(sweep_proxies())
```

Tie `nightly_maintenance` to a cron trigger or a lightweight scheduler.

## 5. Promote to External Storage

When you are ready for persistence, implement the `IStorage` interface or follow
the [PostgreSQL adapter walkthrough](postgres-adapter.md). The worker code above
continues to work unchanged once the storage backend is swapped.
