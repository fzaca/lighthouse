---
title: Run Health Checks at Scale
description: Stream proxy health checks with Pharox and act on the results.
---
# Run Health Checks at Scale

Large proxy pools need consistent, protocol-aware health checks. Pharox provides
`HealthChecker` for lightweight probes and `HealthCheckOrchestrator` when you
want to persist results via `IStorage.apply_health_check_result`.

## 1. Pick the Right Entry Point

| Use case | Entry point |
| --- | --- |
| Ad-hoc validation before leasing | `HealthChecker.check_proxy` |
| Batch sweep with custom storage handling | `HealthChecker.stream_health_checks` |
| Batch sweep that should update storage automatically | `HealthCheckOrchestrator.stream_health_checks` |

## 2. Configure Options Per Protocol

Define defaults and overrides to account for latency differences or HTTP codes.

```python
from pharox import HealthCheckOptions, HealthChecker, ProxyProtocol

checker = HealthChecker(
    default_options=HealthCheckOptions(
        target_url="https://example.com/status/204",
        expected_status_codes=[204],
        timeout=5.0,
        attempts=2,
        slow_threshold_ms=1500,
    )
)

checker.set_protocol_options(
    ProxyProtocol.SOCKS5,
    HealthCheckOptions(
        target_url="https://example.com/ping",
        expected_status_codes=[200],
        timeout=8.0,
        attempts=3,
        slow_threshold_ms=2500,
    ),
)
```

## 3. Stream Results

Feed an iterable of `Proxy` objects. Results arrive as soon as each awaitable
completes.

```python
import asyncio
from pharox import ProxyStatus

async def sweep(proxies):
    async for result in checker.stream_health_checks(proxies):
        if result.status in {ProxyStatus.ACTIVE, ProxyStatus.SLOW}:
            record_success(result)
        else:
            quarantine(result)

active_proxies = my_storage.load_active_proxies()  # implement in your adapter layer
asyncio.run(sweep(active_proxies))
```

## 4. Persist Outcomes Automatically

Use the orchestrator to apply results via the storage adapter.

```python
from pharox import HealthCheckOrchestrator

orchestrator = HealthCheckOrchestrator(storage=my_storage, checker=checker)

async def sweep_and_update():
    proxies = my_storage.load_proxies_for_healthchecks()
    async for result in orchestrator.stream_health_checks(proxies):
        metrics_client.record_latency(result.proxy_id, result.latency_ms)

asyncio.run(sweep_and_update())
```

!!! warning "Storage responsibilities"
    Ensure your adapter's `apply_health_check_result` updates `status`,
    `checked_at`, and any latency metadata so future leases respect fresh
    health data.

## 5. Coordinate with Leasing

Health sweeps often run alongside leasing activity. Recommended pattern:

1. Run `manager.cleanup_expired_leases()` before a sweep to free stale locks.
2. Pause sweeps during peak acquisition bursts, or throttle concurrency.
3. Use callbacks to emit events when a lease is skipped due to health changes.

## 6. Visualise Results

- Feed results into Prometheus/Grafana dashboards (latency histograms, error
  counts per provider).
- Store history in a time-series database for trend analysis.
- Trigger alerts when `ProxyStatus.INACTIVE` exceeds thresholds in a pool.

For a hands-on example, check the `drafts/run_proxy_health_checks.py` script in
the repository or create your own under `examples/health-sweeps/`.
