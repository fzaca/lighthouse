"""Tests for AsyncInMemoryStorage."""
import pytest

from pharox import (
    AsyncInMemoryStorage,
    IAsyncStorage,
)
from pharox.exceptions import PoolNotFoundError
from pharox.models import (
    HealthCheckResult,
    Proxy,
    ProxyProtocol,
    ProxyStatus,
)
from pharox.utils.bootstrap import bootstrap_pool


def _make_proxy(
    pool_id,
    *,
    host: str = "10.0.0.1",
    status: ProxyStatus = ProxyStatus.ACTIVE,
) -> Proxy:
    return Proxy(
        host=host,
        port=8080,
        protocol=ProxyProtocol.HTTP,
        pool_id=pool_id,
        status=status,
    )


@pytest.mark.asyncio
async def test_async_storage_implements_interface() -> None:
    """AsyncInMemoryStorage must satisfy the IAsyncStorage contract."""
    storage = AsyncInMemoryStorage()
    assert isinstance(storage, IAsyncStorage)


@pytest.mark.asyncio
async def test_find_available_proxy_returns_none_for_unknown_pool() -> None:
    """Unknown pool name yields None without raising."""
    storage = AsyncInMemoryStorage()
    result = await storage.find_available_proxy("no-such-pool")
    assert result is None


@pytest.mark.asyncio
async def test_find_available_proxy_returns_proxy() -> None:
    """An active proxy in a registered pool is returned."""
    storage = AsyncInMemoryStorage()
    pool = bootstrap_pool(storage, name="pool-a")
    proxy = _make_proxy(pool.id)
    storage.add_proxy(proxy)

    result = await storage.find_available_proxy("pool-a")
    assert result is not None
    assert result.id == proxy.id


@pytest.mark.asyncio
async def test_ensure_consumer_is_idempotent() -> None:
    """Calling ensure_consumer twice with the same name returns the same ID."""
    storage = AsyncInMemoryStorage()
    id1 = await storage.ensure_consumer("bot-1")
    id2 = await storage.ensure_consumer("bot-1")
    assert id1 == id2


@pytest.mark.asyncio
async def test_create_and_release_lease() -> None:
    """Full acquire → release cycle works end-to-end."""
    storage = AsyncInMemoryStorage()
    pool = bootstrap_pool(storage, name="pool-b")
    proxy = _make_proxy(pool.id)
    storage.add_proxy(proxy)
    await storage.ensure_consumer("worker")

    lease = await storage.create_lease(proxy, "worker", duration_seconds=60)
    assert lease.proxy_id == proxy.id

    await storage.release_lease(lease)

    # Proxy should be available again after release
    result = await storage.find_available_proxy("pool-b")
    assert result is not None


@pytest.mark.asyncio
async def test_cleanup_expired_leases_returns_count() -> None:
    """cleanup_expired_leases is callable and returns an integer."""
    storage = AsyncInMemoryStorage()
    count = await storage.cleanup_expired_leases()
    assert isinstance(count, int)


@pytest.mark.asyncio
async def test_add_proxies_bulk_inserts_all() -> None:
    """add_proxies_bulk inserts every proxy and returns the count."""
    storage = AsyncInMemoryStorage()
    pool = bootstrap_pool(storage, name="pool-bulk")

    proxies = [_make_proxy(pool.id, host=f"10.0.0.{i}") for i in range(1, 6)]
    inserted = await storage.add_proxies_bulk(proxies)
    assert inserted == 5


@pytest.mark.asyncio
async def test_add_proxies_bulk_raises_for_unknown_pool() -> None:
    """add_proxies_bulk raises PoolNotFoundError for an unknown pool_id."""
    from uuid import uuid4

    storage = AsyncInMemoryStorage()
    proxy = _make_proxy(uuid4())  # pool not registered

    with pytest.raises(PoolNotFoundError):
        await storage.add_proxies_bulk([proxy])


@pytest.mark.asyncio
async def test_get_pool_stats_returns_none_for_unknown_pool() -> None:
    """get_pool_stats returns None when the pool does not exist."""
    storage = AsyncInMemoryStorage()
    stats = await storage.get_pool_stats("ghost-pool")
    assert stats is None


@pytest.mark.asyncio
async def test_get_pool_stats_returns_snapshot() -> None:
    """get_pool_stats returns a populated snapshot for a known pool."""
    storage = AsyncInMemoryStorage()
    pool = bootstrap_pool(storage, name="pool-stats")
    storage.add_proxy(_make_proxy(pool.id))

    stats = await storage.get_pool_stats("pool-stats")
    assert stats is not None
    assert stats.pool_name == "pool-stats"
    assert stats.total_proxies == 1


@pytest.mark.asyncio
async def test_apply_health_check_result_updates_proxy() -> None:
    """apply_health_check_result persists status changes."""
    storage = AsyncInMemoryStorage()
    pool = bootstrap_pool(storage, name="pool-hc")
    proxy = _make_proxy(pool.id)
    storage.add_proxy(proxy)

    result = HealthCheckResult(
        proxy_id=proxy.id,
        status=ProxyStatus.INACTIVE,
        latency_ms=999,
        protocol=ProxyProtocol.HTTP,
    )
    updated = await storage.apply_health_check_result(result)
    assert updated is not None
    assert updated.status == ProxyStatus.INACTIVE
