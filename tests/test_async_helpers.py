import pytest

from pharox.async_helpers import (
    acquire_proxy_async,
    release_proxy_async,
    with_lease_async,
)
from pharox.models import ProxyProtocol, ProxyStatus
from pharox.storage.in_memory import InMemoryStorage
from pharox.utils.bootstrap import (
    bootstrap_consumer,
    bootstrap_pool,
    bootstrap_proxy,
)


@pytest.mark.asyncio
async def test_async_acquire_and_release(
    manager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
) -> None:
    """Ensure async helpers acquire and release without blocking."""
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)
    proxy = bootstrap_proxy(
        storage,
        pool=pool,
        host="10.0.0.1",
        port=8080,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        max_concurrency=1,
    )

    lease = await acquire_proxy_async(
        manager,
        pool_name=test_pool_name,
        consumer_name=test_consumer_name,
    )
    assert lease is not None
    assert lease.proxy_id == proxy.id

    await release_proxy_async(manager, lease)
    refreshed_proxy = storage.get_proxy_by_id(proxy.id)
    assert refreshed_proxy is not None
    assert refreshed_proxy.current_leases == 0


@pytest.mark.asyncio
async def test_with_lease_async_always_releases(
    manager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
) -> None:
    """`with_lease_async` should release the lease even on exceptions."""
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)
    proxy = bootstrap_proxy(
        storage,
        pool=pool,
        host="10.0.0.2",
        port=8080,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        max_concurrency=1,
    )

    with pytest.raises(RuntimeError):
        async with with_lease_async(
            manager,
            pool_name=test_pool_name,
            consumer_name=test_consumer_name,
        ) as lease:
            assert lease is not None
            raise RuntimeError("boom")

    refreshed_proxy = storage.get_proxy_by_id(proxy.id)
    assert refreshed_proxy is not None
    assert refreshed_proxy.current_leases == 0
