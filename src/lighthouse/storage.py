from abc import ABC, abstractmethod
from typing import Optional

from lighthouse.models import Lease, Proxy, ProxyFilters


class IStorage(ABC):
    """Abstract interface for storing and managing proxy information."""

    @abstractmethod
    def find_available_proxy(
        self, pool_name: str, filters: Optional[ProxyFilters] = None
    ) -> Optional[Proxy]:
        """Find an active and currently un-leased proxy from the specified pool.

        This method optionally matches a set of filters.

        :param pool_name: The name of the pool to search for an available proxy.
        :param filters: An optional set of criteria to filter the proxies by.
        :return: A Proxy object if one is available, otherwise None.
        """
        pass

    @abstractmethod
    def create_lease(self, proxy: Proxy, client_id: str) -> Lease:
        """Create a new lease for a given proxy and client.

        :param proxy: The proxy to lease.
        :param client_id: The ID of the client requesting the lease.
        :return: The newly created Lease object.
        """
        pass

    @abstractmethod
    def release_lease(self, lease: Lease) -> None:
        """Releases an existing lease.

        :param lease: The lease to release.
        """
        pass
