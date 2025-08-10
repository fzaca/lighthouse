from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from lighthouse.models import Lease, Proxy, ProxyFilters


class IStorage(ABC):
    """Abstract interface for storing and managing proxy information."""

    @abstractmethod
    def find_available_proxy(
        self, pool_name: str, filters: Optional[ProxyFilters] = None
    ) -> Optional[Proxy]:
        """
        Find an available proxy from a named pool that meets the criteria.

        Args:
        ----
            pool_name: The unique name of the pool to search in.
            filters: Optional criteria to filter proxies by.

        Returns
        -------
            A Proxy object if one is available, otherwise None.
        """
        pass

    @abstractmethod
    def create_lease(
        self, proxy: Proxy, client_name: str, duration_seconds: int
    ) -> Lease:
        """
        Create a new lease for a given proxy and client name.

        Args:
        ----
            proxy: The proxy to lease.
            client_name: The name of the client requesting the lease.
            duration_seconds: The duration of the lease in seconds.

        Returns
        -------
            The newly created Lease object.
        """
        pass

    @abstractmethod
    def release_lease(self, lease: Lease) -> None:
        """
        Release an existing lease.

        Args:
        ----
            lease: The lease to release.
        """
        pass

    @abstractmethod
    def cleanup_expired_leases(self) -> int:
        """
        Find and release all expired leases.

        Returns
        -------
            The number of leases that were cleaned up.
        """
        pass
