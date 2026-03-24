---
title: Building a Custom Storage Adapter
description: Implement IStorage to back Pharox with any data store.
---
# Building a Custom Storage Adapter

Pharox uses an `IStorage` interface to decouple proxy lifecycle rules from
persistence. If neither `InMemoryStorage` nor `PostgresStorage` suits your
stack, you can wire in your own backend in one file.

## The Interface

```python
from pharox.storage import IStorage
```

`IStorage` declares eight abstract methods. You must implement all of them:

| Method | What it does |
|--------|--------------|
| `find_available_proxy` | Return one proxy that matches the filters, or `None` |
| `create_lease` | Atomically claim a proxy for a consumer |
| `ensure_consumer` | Upsert a consumer record and return its UUID |
| `release_lease` | Mark a lease as released |
| `cleanup_expired_leases` | Sweep and release all leases past their `expires_at` |
| `apply_health_check_result` | Persist a health-check outcome |
| `get_pool_stats` | Return aggregate counts for a pool |
| `add_proxies_bulk` | Batch-insert proxies in a single operation |

## Minimal Example — Redis-backed Storage

```python
import json
from typing import Optional, Sequence
from uuid import UUID, uuid4

import redis

from pharox.exceptions import ConsumerNotFoundError, PoolNotFoundError
from pharox.models import (
    HealthCheckResult,
    Lease,
    PoolStatsSnapshot,
    Proxy,
    ProxyFilters,
    SelectorStrategy,
)
from pharox.storage import IStorage


class RedisStorage(IStorage):
    """Toy Redis-backed storage adapter.

    This is a simplified illustration. A production implementation should
    handle serialization edge cases, TTLs, and atomic operations via Lua
    scripts or Redis transactions (MULTI/EXEC).
    """

    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _proxy_key(self, proxy_id: UUID) -> str:
        return f"pharox:proxy:{proxy_id}"

    def _pool_key(self, pool_name: str) -> str:
        return f"pharox:pool:{pool_name}"

    def _lease_key(self, lease_id: UUID) -> str:
        return f"pharox:lease:{lease_id}"

    def _consumer_key(self, name: str) -> str:
        return f"pharox:consumer:{name}"

    # ------------------------------------------------------------------
    # IStorage implementation
    # ------------------------------------------------------------------

    def ensure_consumer(self, consumer_name: str) -> UUID:
        """Upsert consumer and return its UUID."""
        key = self._consumer_key(consumer_name)
        existing = self._r.get(key)
        if existing:
            return UUID(existing.decode())
        consumer_id = uuid4()
        self._r.set(key, str(consumer_id))
        return consumer_id

    def find_available_proxy(
        self,
        pool_name: str,
        filters: Optional[ProxyFilters] = None,
        selector: Optional[SelectorStrategy] = None,
    ) -> Optional[Proxy]:
        """Return the first proxy that satisfies the filters."""
        pool_key = self._pool_key(pool_name)
        proxy_ids = self._r.smembers(pool_key)
        for raw_id in proxy_ids:
            proxy_data = self._r.get(self._proxy_key(UUID(raw_id.decode())))
            if not proxy_data:
                continue
            proxy = Proxy.model_validate_json(proxy_data)
            if filters and not filters.matches(proxy):
                continue
            return proxy
        return None

    def create_lease(
        self, proxy: Proxy, consumer_name: str, duration_seconds: int
    ) -> Lease:
        """Create a lease — simplified; not atomic in this example."""
        consumer_id = self._r.get(self._consumer_key(consumer_name))
        if not consumer_id:
            raise ConsumerNotFoundError(f"Consumer '{consumer_name}' not found.")

        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        lease = Lease(
            proxy_id=proxy.id,
            consumer_id=UUID(consumer_id.decode()),
            pool_id=proxy.pool_id,
            acquired_at=now,
            expires_at=now + timedelta(seconds=duration_seconds),
        )
        self._r.setex(
            self._lease_key(lease.id),
            duration_seconds,
            lease.model_dump_json(),
        )
        return lease

    def release_lease(self, lease: Lease) -> None:
        """Delete the lease key."""
        self._r.delete(self._lease_key(lease.id))

    def cleanup_expired_leases(self) -> int:
        # Redis TTL handles expiry automatically; nothing to sweep.
        return 0

    def apply_health_check_result(
        self, result: HealthCheckResult
    ) -> Optional[Proxy]:
        """Update stored proxy status."""
        key = self._proxy_key(result.proxy_id)
        raw = self._r.get(key)
        if not raw:
            return None
        proxy = Proxy.model_validate_json(raw)
        proxy.status = result.status
        proxy.checked_at = result.checked_at
        self._r.set(key, proxy.model_dump_json())
        return proxy

    def get_pool_stats(self, pool_name: str) -> Optional[PoolStatsSnapshot]:
        """Return basic counts for a pool."""
        pool_key = self._pool_key(pool_name)
        if not self._r.exists(pool_key):
            return None
        proxy_ids = self._r.smembers(pool_key)
        proxies = []
        for raw_id in proxy_ids:
            raw = self._r.get(self._proxy_key(UUID(raw_id.decode())))
            if raw:
                proxies.append(Proxy.model_validate_json(raw))
        return PoolStatsSnapshot(
            pool_name=pool_name,
            total_proxies=len(proxies),
        )

    def add_proxies_bulk(self, proxies: Sequence[Proxy]) -> int:
        """Store all proxies and register them in their pools."""
        if not proxies:
            return 0
        pipe = self._r.pipeline()
        for proxy in proxies:
            pipe.set(self._proxy_key(proxy.id), proxy.model_dump_json())
            pipe.sadd(self._pool_key(proxy.pool_id), str(proxy.id))
        pipe.execute()
        return len(proxies)
```

## Wiring It Up

```python
import redis
from pharox import ProxyManager

r = redis.Redis(host="localhost", port=6379, db=0)
storage = RedisStorage(r)
manager = ProxyManager(storage=storage)
```

## Async Variant

If you prefer an async adapter, implement `IAsyncStorage` instead:

```python
from pharox.storage.async_interface import IAsyncStorage

class AsyncRedisStorage(IAsyncStorage):
    """Async Redis adapter using redis.asyncio."""

    def __init__(self, client) -> None:  # redis.asyncio.Redis
        self._r = client

    async def find_available_proxy(self, pool_name, filters=None, selector=None):
        ...  # same logic with await self._r.smembers / get
```

Then pass it to `HealthCheckOrchestrator`:

```python
from pharox import HealthCheckOrchestrator

orchestrator = HealthCheckOrchestrator(storage=async_storage)
```

## Testing Your Adapter

Use the `StorageContractFixtures` + `storage_contract_suite` helpers from
`pharox.tests.adapters` to run the standard contract test suite against your
implementation:

```python
# tests/test_redis_adapter.py
from pharox.tests.adapters import StorageContractFixtures, storage_contract_suite
from my_app.storage import RedisStorage

def test_redis_adapter_contract():
    fixtures = StorageContractFixtures(
        make_storage=lambda: RedisStorage(fake_redis_client()),
        seed_pool=lambda s, p: s._r.sadd(f"pharox:meta:pool:{p.name}", str(p.id)),
        seed_proxy=lambda s, p: s._r.set(f"pharox:proxy:{p.id}", p.model_dump_json()),
    )
    storage_contract_suite(fixtures)
```

The suite exercises all eight interface methods and verifies edge cases like
duplicate releases, expired lease cleanup, and filter matching.
