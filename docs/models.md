# Models & Filters

The toolkit ships Pydantic models that describe proxies, leases, and filtering
options. These classes are shared across the SDK and service, so treating them
as your contract keeps every integration aligned.

## Proxy

```python
from pharox import Proxy, ProxyProtocol, ProxyStatus

proxy = Proxy(
    host="186.33.123.10",
    port=8080,
    protocol=ProxyProtocol.HTTP,
    pool_id=pool.id,
    status=ProxyStatus.ACTIVE,
    country="AR",
    source="oxylabs",
)

print(proxy.url)  # http://186.33.123.10:8080
```

Important fields:

- `protocol` accepts HTTP, HTTPS, SOCKS4, or SOCKS5.
- `credentials` can hold user/password pairs. The `url` property encodes them
  automatically for client libraries like `httpx` or `requests`.
- `max_concurrency` limits simultaneous leases. `None` means unlimited.
- `current_leases` is managed by the storage adapter; treat it as read-only.

## ProxyPool

Pools group proxies with shared configuration. Use pool names to pick distinct
provider buckets or geographic segments.

```python
from pharox import ProxyPool

pool = ProxyPool(name="latam-residential", description="Residential LatAm proxies")
```

## Consumers

A `Consumer` identifies the actor leasing proxies. This can be a worker name,
a service, or any identifier meaningful to your system.

```python
from pharox import Consumer

storage.add_consumer(Consumer(name="worker-1"))
```

## Leases

`Lease` records who is using a proxy and when the access expires. You usually
interact with this through `ProxyManager.acquire_proxy`, but the data model is
available if you need to persist or audit leases.

```python
lease.id
lease.proxy_id
lease.expires_at
```

## Proxy Filters

`ProxyFilters` lets you express selection criteria. All fields are optional, and
adapters decide how to evaluate them.

```python
from pharox import ProxyFilters

filters = ProxyFilters(
    country="CO",
    source="latam-provider",
    asn=12345,
    latitude=4.7110,
    longitude=-74.0721,
    radius_km=50,
)
```

Validation rules:

- Latitude and longitude must appear together.
- If `radius_km` is set, geolocation coordinates are required.

## Status Enums

Both proxies and leases expose enums for their lifecycle.

```python
from pharox import ProxyStatus, LeaseStatus

if result.status is ProxyStatus.SLOW:
    ...

if lease.status is LeaseStatus.RELEASED:
    ...
```

Stay consistent with these enums when writing storage adapters or APIs so that
all Pharox components can reason about state transitions identically.
