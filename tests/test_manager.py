from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from uuid import UUID, uuid4

import pytest

from lighthouse.manager import ProxyManager
from lighthouse.models import Lease, Proxy, ProxyFilters, ProxyStatus
from lighthouse.storage import IStorage


class MockStorage(IStorage):
    """A mock implementation of IStorage that operates in memory."""

    def __init__(self):
        """Initialize the mock storage."""
        self.proxies: Dict[UUID, Proxy] = {}
        self.leases: Dict[UUID, Lease] = {}

    def find_available_proxy(
        self, pool_name: str, filters: Optional[ProxyFilters] = None
    ) -> Optional[Proxy]:
        """Find an available proxy in the mock storage."""
        for proxy in self.proxies.values():
            if proxy.pool_name == pool_name and proxy.status == ProxyStatus.ACTIVE:
                if (
                    proxy.max_concurrency is None
                    or proxy.current_leases < proxy.max_concurrency
                ):
                    return proxy
        return None

    def create_lease(
        self, proxy: Proxy, client_id: str, duration_seconds: int
    ) -> Lease:
        """Create a lease in the mock storage."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=duration_seconds)
        lease = Lease(
            proxy_id=proxy.id,
            client_id=UUID(client_id),  # Assuming client_id is a UUID string
            expires_at=expires_at,
            acquired_at=now,
        )
        self.leases[lease.id] = lease

        # Atomically increment lease count
        proxy_to_update = self.proxies[proxy.id]
        proxy_to_update.current_leases += 1

        return lease

    def release_lease(self, lease: Lease) -> None:
        """Release a lease in the mock storage."""
        if lease.id in self.leases:
            proxy = self.proxies.get(lease.proxy_id)
            if proxy and proxy.current_leases > 0:
                proxy.current_leases -= 1
            # In a real scenario, we'd also mark the lease as 'released'
            # For this test, simply decrementing the count is sufficient.
            # del self.leases[lease.id]

    def cleanup_expired_leases(self) -> int:
        """Clean up expired leases in the mock storage."""
        # Not needed for these tests
        return 0

    # Helper to add proxies for tests
    def add_proxy(self, proxy: Proxy):
        """Add a proxy to the mock storage."""
        self.proxies[proxy.id] = proxy


@pytest.fixture
def mock_storage() -> MockStorage:
    """Provide a clean instance of MockStorage for each test."""
    return MockStorage()


@pytest.fixture
def proxy_manager(mock_storage: MockStorage) -> ProxyManager:
    """Provide a ProxyManager instance initialized with MockStorage."""
    return ProxyManager(mock_storage)


def test_acquire_exclusive_proxy_success_and_fail(
    proxy_manager: ProxyManager, mock_storage: MockStorage
):
    """Test that a proxy with max_concurrency=1 can only be leased once."""
    proxy = Proxy(
        host="127.0.0.1",
        port=8080,
        protocol="http",
        pool_name="test_pool",
        status=ProxyStatus.ACTIVE,
        max_concurrency=1,
    )
    mock_storage.add_proxy(proxy)

    # First acquisition should succeed
    lease = proxy_manager.acquire_proxy(
        pool_name="test_pool", client_id=str(uuid4())
    )
    assert lease is not None
    assert lease.proxy_id == proxy.id
    assert mock_storage.proxies[proxy.id].current_leases == 1

    # Second acquisition should fail
    second_lease = proxy_manager.acquire_proxy(
        pool_name="test_pool", client_id=str(uuid4())
    )
    assert second_lease is None
    assert mock_storage.proxies[proxy.id].current_leases == 1


def test_acquire_shared_proxy_up_to_limit(
    proxy_manager: ProxyManager, mock_storage: MockStorage
):
    """Test that a proxy with max_concurrency=3 can be leased three times."""
    proxy = Proxy(
        host="127.0.0.1",
        port=8081,
        protocol="http",
        pool_name="shared_pool",
        status=ProxyStatus.ACTIVE,
        max_concurrency=3,
    )
    mock_storage.add_proxy(proxy)

    # Acquire three times, should all succeed
    for i in range(3):
        lease = proxy_manager.acquire_proxy(
            pool_name="shared_pool", client_id=str(uuid4())
        )
        assert lease is not None
        assert mock_storage.proxies[proxy.id].current_leases == i + 1

    # Fourth acquisition should fail
    fail_lease = proxy_manager.acquire_proxy(
        pool_name="shared_pool", client_id=str(uuid4())
    )
    assert fail_lease is None
    assert mock_storage.proxies[proxy.id].current_leases == 3


def test_acquire_unlimited_proxy(
    proxy_manager: ProxyManager, mock_storage: MockStorage
):
    """Test that a proxy with max_concurrency=None can be leased many times."""
    proxy = Proxy(
        host="127.0.0.1",
        port=8082,
        protocol="http",
        pool_name="unlimited_pool",
        status=ProxyStatus.ACTIVE,
        max_concurrency=None,  # Unlimited
    )
    mock_storage.add_proxy(proxy)

    # Acquire 10 times, should all succeed
    for i in range(10):
        lease = proxy_manager.acquire_proxy(
            pool_name="unlimited_pool", client_id=str(uuid4())
        )
        assert lease is not None
        assert mock_storage.proxies[proxy.id].current_leases == i + 1


def test_release_frees_up_slot(proxy_manager: ProxyManager, mock_storage: MockStorage):
    """Test that releasing a lease makes a slot available again."""
    proxy = Proxy(
        host="127.0.0.1",
        port=8083,
        protocol="http",
        pool_name="release_pool",
        status=ProxyStatus.ACTIVE,
        max_concurrency=1,
    )
    mock_storage.add_proxy(proxy)

    # 1. Acquire the proxy
    lease = proxy_manager.acquire_proxy(
        pool_name="release_pool", client_id=str(uuid4())
    )
    assert lease is not None
    assert mock_storage.proxies[proxy.id].current_leases == 1

    # 2. Try to acquire again, should fail
    failed_acquisition = proxy_manager.acquire_proxy(
        pool_name="release_pool", client_id=str(uuid4())
    )
    assert failed_acquisition is None

    # 3. Release the first lease
    proxy_manager.release_proxy(lease)
    assert mock_storage.proxies[proxy.id].current_leases == 0

    # 4. Acquire again, should succeed
    second_lease = proxy_manager.acquire_proxy(
        pool_name="release_pool", client_id=str(uuid4())
    )
    assert second_lease is not None
    assert mock_storage.proxies[proxy.id].current_leases == 1
