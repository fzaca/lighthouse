from pharox.models import Proxy, ProxyPool
from pharox.storage.in_memory import InMemoryStorage
from pharox.tests.adapters import (
    StorageContractFixtures,
    storage_contract_suite,
)


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
