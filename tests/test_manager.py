from typing import Optional

from lighthouse.manager import ProxyManager
from lighthouse.models import Lease, Proxy, ProxyFilters
from lighthouse.storage import IStorage


class MockStorage(IStorage):
    """A mock implementation of the IStorage interface for testing purposes."""

    def find_available_proxy(
        self, pool_name: str, filters: Optional[ProxyFilters] = None
    ) -> Optional[Proxy]:
        """Mock implementation of find_available_proxy."""
        pass

    def create_lease(self, proxy: Proxy, client_id: str) -> Lease:
        """Mock implementation of create_lease."""
        pass

    def release_lease(self, lease: Lease) -> None:
        """Mock implementation of release_lease."""
        pass


def test_proxy_manager_instantiation():
    """Test that the ProxyManager can be instantiated successfully."""
    mock_storage = MockStorage()
    proxy_manager = ProxyManager(storage=mock_storage)
    assert proxy_manager is not None, "ProxyManager should be instantiable."
