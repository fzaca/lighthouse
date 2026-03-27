import pytest

from pharox.exceptions import PoolNotFoundError, ProxyNotFoundError
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


# ------------------------------------------------------------------
# CRUD tests
# ------------------------------------------------------------------

def test_save_and_get_pool() -> None:
    """save_pool persists and get_pool retrieves by ID."""
    storage = InMemoryStorage()
    pool = ProxyPool(name="crud-pool", description="desc")
    storage.save_pool(pool)
    result = storage.get_pool(str(pool.id))
    assert result.name == "crud-pool"
    assert result.description == "desc"


def test_get_pool_not_found() -> None:
    """get_pool raises PoolNotFoundError for an unknown ID."""
    from uuid import uuid4
    storage = InMemoryStorage()
    with pytest.raises(PoolNotFoundError):
        storage.get_pool(str(uuid4()))


def test_list_pools() -> None:
    """list_pools returns all persisted pools."""
    storage = InMemoryStorage()
    storage.save_pool(ProxyPool(name="p1"))
    storage.save_pool(ProxyPool(name="p2"))
    pools = storage.list_pools()
    assert {p.name for p in pools} == {"p1", "p2"}


def test_delete_pool() -> None:
    """delete_pool removes a pool; subsequent get_pool raises."""
    storage = InMemoryStorage()
    pool = ProxyPool(name="to-delete")
    storage.save_pool(pool)
    storage.delete_pool(str(pool.id))
    with pytest.raises(PoolNotFoundError):
        storage.get_pool(str(pool.id))


def test_save_and_get_proxy() -> None:
    """save_proxy persists and get_proxy retrieves by ID."""
    storage = InMemoryStorage()
    pool = ProxyPool(name="pp")
    storage.save_pool(pool)
    proxy = Proxy(
        host="1.2.3.4", port=8080, protocol=ProxyProtocol.HTTP, pool_id=pool.id
    )
    storage.save_proxy(proxy)
    result = storage.get_proxy(str(proxy.id))
    assert result.host == proxy.host


def test_get_proxy_not_found() -> None:
    """get_proxy raises ProxyNotFoundError for an unknown ID."""
    from uuid import uuid4
    storage = InMemoryStorage()
    with pytest.raises(ProxyNotFoundError):
        storage.get_proxy(str(uuid4()))


def test_list_proxies() -> None:
    """list_proxies returns all proxies in a pool."""
    storage = InMemoryStorage()
    pool = ProxyPool(name="lp")
    storage.save_pool(pool)
    for i in range(3):
        storage.save_proxy(
            Proxy(
                host=f"10.0.0.{i}", port=8080,
                protocol=ProxyProtocol.HTTP, pool_id=pool.id,
            )
        )
    proxies = storage.list_proxies(str(pool.id))
    assert len(proxies) == 3


def test_delete_proxy() -> None:
    """delete_proxy removes a proxy; subsequent get_proxy raises."""
    storage = InMemoryStorage()
    pool = ProxyPool(name="dp")
    storage.save_pool(pool)
    proxy = Proxy(
        host="5.6.7.8", port=3128, protocol=ProxyProtocol.HTTP, pool_id=pool.id
    )
    storage.save_proxy(proxy)
    storage.delete_proxy(str(proxy.id))
    with pytest.raises(ProxyNotFoundError):
        storage.get_proxy(str(proxy.id))


def test_get_and_list_leases() -> None:
    """get_lease and list_leases return correct lease objects."""
    storage = InMemoryStorage()
    pool = ProxyPool(name="lp2")
    storage.save_pool(pool)
    proxy = Proxy(
        host="1.1.1.1", port=80, protocol=ProxyProtocol.HTTP,
        pool_id=pool.id, status=ProxyStatus.ACTIVE,
    )
    storage.save_proxy(proxy)

    consumer_id = storage.ensure_consumer("test-consumer")
    lease = storage.create_lease(proxy, "test-consumer", 300)

    fetched = storage.get_lease(str(lease.id))
    assert fetched is not None
    assert fetched.id == lease.id

    leases = storage.list_leases(str(consumer_id))
    assert any(item.id == lease.id for item in leases)

    all_leases = storage.list_leases()
    assert any(item.id == lease.id for item in all_leases)


def test_get_lease_not_found() -> None:
    """get_lease returns None for an unknown ID."""
    from uuid import uuid4
    storage = InMemoryStorage()
    assert storage.get_lease(str(uuid4())) is None
