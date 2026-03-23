import pytest

from pharox.exceptions import PoolNotFoundError
from pharox.models import Proxy, ProxyPool, ProxyProtocol, ProxyStatus
from pharox.storage.in_memory import InMemoryStorage
from pharox.tests.adapters import (
    StorageContractFixtures,
    storage_contract_suite,
)
from pharox.utils.bootstrap import bootstrap_pool


def _make_storage() -> InMemoryStorage:
    return InMemoryStorage()


def _seed_pool(storage: InMemoryStorage, pool: ProxyPool) -> ProxyPool:
    storage.add_pool(pool)
    return pool


def _seed_proxy(storage: InMemoryStorage, proxy: Proxy) -> Proxy:
    storage.add_proxy(proxy)
    return proxy


def test_in_memory_storage_conforms_to_contract():
    """Ensure InMemoryStorage satisfies the standard adapter contract."""
    fixtures = StorageContractFixtures(
        make_storage=_make_storage,
        seed_pool=_seed_pool,
        seed_proxy=_seed_proxy,
    )
    storage_contract_suite(fixtures)


def test_add_proxies_bulk_inserts_all_proxies() -> None:
    """add_proxies_bulk should add all proxies under a single lock."""
    storage = InMemoryStorage()
    pool = bootstrap_pool(storage, name="bulk-pool")

    proxies = [
        Proxy(
            host=f"10.0.0.{i}",
            port=8080,
            protocol=ProxyProtocol.HTTP,
            pool_id=pool.id,
            status=ProxyStatus.ACTIVE,
        )
        for i in range(1, 6)
    ]
    count = storage.add_proxies_bulk(proxies)

    assert count == 5
    for proxy in proxies:
        assert storage.get_proxy_by_id(proxy.id) is not None


def test_add_proxies_bulk_returns_zero_for_empty_input() -> None:
    """add_proxies_bulk should be a no-op for an empty list."""
    storage = InMemoryStorage()
    assert storage.add_proxies_bulk([]) == 0


def test_add_proxies_bulk_raises_for_unknown_pool() -> None:
    """add_proxies_bulk should raise PoolNotFoundError for missing pool."""
    from uuid import uuid4

    storage = InMemoryStorage()
    proxy = Proxy(
        host="1.1.1.1",
        port=80,
        protocol=ProxyProtocol.HTTP,
        pool_id=uuid4(),  # unknown pool
    )

    with pytest.raises(PoolNotFoundError):
        storage.add_proxies_bulk([proxy])
