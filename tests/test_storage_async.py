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


@pytest.mark.asyncio
async def test_lowest_latency_selector_picks_fastest() -> None:
    """LOWEST_LATENCY selector returns the proxy with the smallest latency_ms."""
    from pharox import SelectorStrategy

    storage = AsyncInMemoryStorage()
    pool = bootstrap_pool(storage, name="pool-latency")

    slow = _make_proxy(pool.id, host="10.0.0.10")
    fast = _make_proxy(pool.id, host="10.0.0.20")
    medium = _make_proxy(pool.id, host="10.0.0.30")
    for p in (slow, fast, medium):
        storage.add_proxy(p)

    for proxy, latency in ((slow, 1500), (fast, 200), (medium, 800)):
        await storage.apply_health_check_result(
            HealthCheckResult(
                proxy_id=proxy.id,
                status=ProxyStatus.ACTIVE,
                latency_ms=latency,
                protocol=ProxyProtocol.HTTP,
            )
        )

    chosen = await storage.find_available_proxy(
        "pool-latency", selector=SelectorStrategy.LOWEST_LATENCY
    )
    assert chosen is not None
    assert str(chosen.host) == "10.0.0.20"


@pytest.mark.asyncio
async def test_lowest_latency_proxies_without_health_result_go_last() -> None:
    """Proxies with no health result are deprioritized over any measured latency."""
    from pharox import SelectorStrategy

    storage = AsyncInMemoryStorage()
    pool = bootstrap_pool(storage, name="pool-latency-fallback")

    no_check = _make_proxy(pool.id, host="10.0.1.1")
    checked = _make_proxy(pool.id, host="10.0.1.2")
    for p in (no_check, checked):
        storage.add_proxy(p)

    await storage.apply_health_check_result(
        HealthCheckResult(
            proxy_id=checked.id,
            status=ProxyStatus.ACTIVE,
            latency_ms=5000,
            protocol=ProxyProtocol.HTTP,
        )
    )

    chosen = await storage.find_available_proxy(
        "pool-latency-fallback", selector=SelectorStrategy.LOWEST_LATENCY
    )
    assert chosen is not None
    assert str(chosen.host) == "10.0.1.2"


@pytest.mark.asyncio
async def test_get_last_health_result() -> None:
    """get_last_health_result returns the most recent HealthCheckResult."""
    storage = AsyncInMemoryStorage()
    pool = bootstrap_pool(storage, name="pool-last-hc")
    proxy = _make_proxy(pool.id)
    storage.add_proxy(proxy)

    assert await storage.get_last_health_result(proxy.id) is None

    result = HealthCheckResult(
        proxy_id=proxy.id,
        status=ProxyStatus.ACTIVE,
        latency_ms=350,
        protocol=ProxyProtocol.HTTP,
    )
    await storage.apply_health_check_result(result)

    stored = await storage.get_last_health_result(proxy.id)
    assert stored is not None
    assert stored.latency_ms == 350
    assert stored.proxy_id == proxy.id
