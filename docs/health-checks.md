# Health Checking Toolkit

Every Lighthouse deployment needs a consistent, repeatable way to verify that
proxies are reachable and responsive. The health module bundles that logic so
scripts, SDK workers, and services all classify proxies the same way.

## Key Building Blocks

- **`HealthCheckOptions`** (`lighthouse.models`): runtime configuration for a
  probe (target URL, attempts, timeout, expected status codes, latency
  threshold, request headers, redirect policy).
- **`HealthChecker`** (`lighthouse.health`): orchestrates checks, choosing the
  strategy that matches each proxy’s protocol and returning a
  `HealthCheckResult`.
- **`HTTPHealthCheckStrategy`**: default strategy used for HTTP, HTTPS, SOCKS4,
  and SOCKS5 proxies. It performs real HTTP requests through the proxy and
  classifies the result as `active`, `slow`, or `inactive`.

> **Note**: SOCKS support relies on `httpx[socks]`. Install it with
> `pip install lighthouse[socks]` or `pip install httpx[socks]` if you plan to
> probe SOCKS4/5 endpoints.

You can register additional strategies for custom protocols or handshake
behaviour, while reusing the rest of the orchestration logic.

## Quick Example

```python
import asyncio
from uuid import uuid4

from lighthouse import HealthCheckOptions, HealthChecker, Proxy, ProxyProtocol

proxy = Proxy(
    host="dc.oxylabs.io",
    port=8001,
    protocol=ProxyProtocol.HTTP,
    pool_id=uuid4(),  # replace with an existing pool ID in your storage
)

checker = HealthChecker()
options = HealthCheckOptions(
    target_url="https://example.com/status/204",
    expected_status_codes=[204],
    attempts=2,
    timeout=5.0,
)

result = asyncio.run(checker.check_proxy(proxy, options=options))
print(result.status, result.latency_ms, result.status_code)
```

## Options Reference

| Field | Purpose | Tips |
| ----- | ------- | ---- |
| `target_url` | Endpoint hit through the proxy | Use a low-latency endpoint under your control when possible. |
| `timeout` | Per-attempt timeout (seconds) | Keep conservative defaults; health checks should fail fast. |
| `attempts` | Maximum retries | Combine with `expected_status_codes` to tolerate transient errors. |
| `expected_status_codes` | Acceptable HTTP codes | Include every success code returned by your target URL. |
| `slow_threshold_ms` | Latency boundary between `active` and `slow` | Tune per workload. `slow` still indicates connectivity. |
| `headers` | Extra request headers | Useful for provider auth tokens or tracing headers. |
| `allow_redirects` | Follow HTTP redirects | Disable when you want to detect 3xx responses explicitly. |

## Batch Checks with Streaming

`HealthChecker.stream_health_checks` launches checks concurrently and yields
results as they complete:

```python
from lighthouse import ProxyStatus

async def sweep(proxies):
    checker = HealthChecker()
    async for result in checker.stream_health_checks(proxies):
        if result.status in {ProxyStatus.ACTIVE, ProxyStatus.SLOW}:
            handle_healthy_proxy(result)
        else:
            handle_unhealthy_proxy(result)

asyncio.run(sweep(proxy_list))
```

This pattern is ideal for scheduled health workers or on-demand diagnostics.
The async generator keeps memory usage predictable even when you probe large
lists.

## Integrating with `ProxyManager`

Health checks often precede or follow leasing operations:

1. Acquire a candidate proxy using `ProxyManager.acquire_proxy`.
2. Run a health check with the desired options.
3. Release the lease if the proxy fails or exhibits high latency.

```python
from lighthouse import ProxyStatus

async def acquire_and_probe(manager, storage, checker):
    lease = manager.acquire_proxy(pool_name="latam-residential")
    if not lease:
        return None

    proxy = storage.get_proxy_by_id(lease.proxy_id)
    health = await checker.check_proxy(proxy)
    if health.status is ProxyStatus.INACTIVE:
        manager.release_proxy(lease)
        return None
    return lease
```

The workflow mirrors the behaviour you’ll deploy in the FastAPI service or SDK
workers, ensuring both components make consistent decisions.

## Custom Strategies

Some environments require protocol-specific probes (for example, negotiating a
SOCKS5 authentication step or verifying a proprietary tunnel). Implement
`HealthCheckStrategy` and register it for the relevant protocol:

```python
from lighthouse import ProxyProtocol
from lighthouse.health import HealthCheckStrategy, HealthChecker

class RedisTunnelStrategy(HealthCheckStrategy):
    async def check(self, proxy, options):
        ...  # perform tunnel handshake and return HealthCheckResult

checker = HealthChecker()
checker.register_strategy(ProxyProtocol.SOCKS5, RedisTunnelStrategy())
```

## Storing and Acting on Results

`HealthCheckResult` captures:

- `status` (`ProxyStatus.ACTIVE`, `SLOW`, or `INACTIVE`)
- `latency_ms` (per successful attempt or timeout duration)
- `attempts` used before reaching a decision
- `status_code` and optional `error_message`
- `checked_at` timestamp (UTC)

Persist these results in your own layer if you need historical analytics or
automated remediation. The toolkit intentionally stops short of storing
anything so it stays embeddable in any environment.

## Local Testing Helpers

The repository includes `drafts/run_proxy_health_checks.py`, a small script that
seeds `InMemoryStorage`, leases proxies, and runs simple or bulk health checks.
Use it as a reference when wiring the toolkit to real providers or when
debugging proxy credentials.
