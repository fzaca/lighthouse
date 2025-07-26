from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from lighthouse.models import Lease, Proxy, ProxyFilters, ProxyStatus


class IStorage(ABC):
    """Abstract interface for storing and managing proxy information."""

    @abstractmethod
    def find_available_proxy(
        self, pool_name: str, filters: Optional[ProxyFilters] = None
    ) -> Optional[Proxy]:
        """Find an available proxy that meets the concurrency criteria.

        This method finds a proxy where the status is 'active' AND
        ((max_concurrency is None) OR (current_leases < max_concurrency)).
        It also optionally matches a set of filters.

        Args:
            pool_name: The name of the pool to search in.
            filters: Optional criteria to filter proxies by.

        Returns
        -------
        Optional[Proxy]
            A Proxy object if one is available, otherwise None.
        """
        pass

    @abstractmethod
    def create_lease(
        self, proxy: Proxy, client_id: str, duration_seconds: int
    ) -> Lease:
        """Create a new lease for a given proxy and client for a specific duration.

        This method calculates the `expires_at` field for the new lease based
        on the current time and the provided `duration_seconds`. It is also
        responsible for atomically incrementing the `current_leases` count on
        the associated proxy.

        Args:
            proxy: The proxy to lease.
            client_id: The ID of the client requesting the lease.
            duration_seconds: The duration of the lease in seconds.

        Returns
        -------
        Lease
            The newly created Lease object.
        """
        pass

    @abstractmethod
    def release_lease(self, lease: Lease) -> None:
        """Release an existing lease.

        This method is responsible for atomically decrementing the
        `current_leases` count on the associated proxy.

        Args:
            lease: The lease to release.
        """
        pass

    @abstractmethod
    def cleanup_expired_leases(self) -> int:
        """Find and release all expired leases.

        This method should find all leases where `expires_at` is in the past
        and `status` is 'active'. It should then release them, decrementing
        the `current_leases` count on their respective proxies.

        Returns
        -------
        int
            The number of leases that were cleaned up.
        """
        pass

    @abstractmethod
    def get_proxies_to_check(self, limit: int = 100) -> list[Proxy]:
        """Fetch a list of proxies due for a health check."""
        pass

    @abstractmethod
    def update_proxy_health(
        self, proxy_id: str, status: "ProxyStatus", latency: float
    ) -> None:
        """Update the health status and latency for a specific proxy."""
        pass
