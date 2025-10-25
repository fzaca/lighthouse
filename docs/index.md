# Lighthouse Toolkit

<div class="hero">
  <div>
    <h1>Ship proxy logic with confidence</h1>
    <p>Lighthouse Core keeps proxy lifecycle rules in one place so your services,
    workers, and scripts act consistently. Lease, monitor, and recycle proxies
    with battle-tested business logic.</p>
    <div class="cta">
      <a class="primary" href="proxy-manager/">Dive into the Proxy Manager</a>
      <a class="secondary" href="https://github.com/fzaca/lighthouse" target="_blank" rel="noopener">View on GitHub</a>
    </div>
  </div>
</div>

<div class="feature-grid">
  <div class="feature-card">
    <h3>Proxy lifecycle management</h3>
    <p>Acquire, renew, and release leases with built-in concurrency rules.</p>
    <ul>
      <li>Exclusive, shared, and unlimited lease modes</li>
      <li>Automatic lease cleanup hooks</li>
      <li>Transparent instrumentation points</li>
    </ul>
  </div>
  <div class="feature-card">
    <h3>Composable storage adapters</h3>
    <p>Implement the `IStorage` interface once and reuse it everywhere.</p>
    <ul>
      <li>In-memory adapter for local scripts</li>
      <li>Drop-in room for Postgres, Redis, or your datastore</li>
      <li>Shared schema across SDK and services</li>
    </ul>
  </div>
  <div class="feature-card">
    <h3>Health insights that travel</h3>
    <p>Consistent HTTP/SOCKS checks your automation and APIs can trust.</p>
    <ul>
      <li>Async probing with configurable thresholds</li>
      <li>Structured results for dashboards or alerts</li>
      <li>Integrates with leasing flows out of the box</li>
    </ul>
  </div>
</div>

## Quickstart

Install the package from PyPI and wire the in-memory storage to experiment
locally:

```bash
pip install lighthouse
```

```python
from lighthouse import (
    Consumer,
    InMemoryStorage,
    Proxy,
    ProxyManager,
    ProxyPool,
    ProxyStatus,
)

storage = InMemoryStorage()
manager = ProxyManager(storage=storage)

# Seed a default consumer and pool
consumer = Consumer(name=manager.DEFAULT_CONSUMER_NAME)
storage.add_consumer(consumer)
pool = ProxyPool(name="latam-residential")
storage.add_pool(pool)

storage.add_proxy(
    Proxy(
        host="1.1.1.1",
        port=8080,
        protocol="http",
        pool_id=pool.id,
        status=ProxyStatus.ACTIVE,
    )
)

lease = manager.acquire_proxy(pool_name=pool.name)
if lease:
    print("Proxy leased!", lease.proxy_id)
    manager.release_proxy(lease)
```

For more advanced examples and real-host testing, explore the draft script in
`drafts/run_proxy_health_checks.py`.

## Where to Go Next

- Understand leasing flows in the [Proxy Manager guide](proxy-manager.md).
- Review available models and filters in [Models & Filters](models.md).
- Explore the configurable [Health Checks](health-checks.md).
- Learn how to plug your database in [Storage Adapters](storage.md).
- Visit the GitHub repository for issue tracking and release notes:
  <https://github.com/fzaca/lighthouse>.
