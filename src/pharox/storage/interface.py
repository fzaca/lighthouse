from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Sequence
from uuid import UUID

from ..models import (
    HealthCheckResult,
    Lease,
    PoolStatsSnapshot,
    Proxy,
    ProxyFilters,
    ProxyPool,
    SelectorStrategy,
)


class IStorage(ABC):
    """Abstract interface for storing and managing proxy information."""

    @abstractmethod
    def find_available_proxy(
        self,
        pool_name: str,
        filters: Optional[ProxyFilters] = None,
        selector: Optional[SelectorStrategy] = None,
    ) -> Optional[Proxy]:
        """
        Find an available proxy from a named pool that meets the criteria.

        Args:
        ----
            pool_name: The unique name of the pool to search in.
            filters: Optional criteria to filter proxies by.
            selector: Strategy hint for how to pick between available proxies.

        Returns
        -------
            A Proxy object if one is available, otherwise None.
        """
        pass

    @abstractmethod
    def create_lease(
        self, proxy: Proxy, consumer_name: str, duration_seconds: int
    ) -> Lease:
        """
        Create a new lease for a given proxy and consumer name.

        Args:
        ----
            proxy: The proxy to lease.
            consumer_name: The name of the entity requesting the lease.
            duration_seconds: The duration of the lease in seconds.

        Returns
        -------
            The newly created Lease object.
        """
        pass

    @abstractmethod
    def ensure_consumer(self, consumer_name: str) -> UUID:
        """Ensure a consumer entry exists and return its ID."""
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

    @abstractmethod
    def apply_health_check_result(
        self, result: HealthCheckResult
    ) -> Optional[Proxy]:
        """
        Persist the outcome of a health check for a proxy.

        Args:
        ----
            result: Result data produced by a health check execution.

        Returns
        -------
            A copy of the updated proxy, or None if the proxy was not found.
        """
        pass

    @abstractmethod
    def get_last_health_result(
        self, proxy_id: UUID
    ) -> Optional[HealthCheckResult]:
        """
        Return the most recent health check result for a proxy.

        Returns
        -------
            The last HealthCheckResult, or None if no check has been run.
        """
        pass

    @abstractmethod
    def get_pool_stats(self, pool_name: str) -> Optional[PoolStatsSnapshot]:
        """Return aggregate stats for a pool."""
        pass

    @abstractmethod
    def add_proxies_bulk(self, proxies: Sequence[Proxy]) -> int:
        """
        Add multiple proxies in a single operation.

        Args:
        ----
            proxies: The proxy objects to add.

        Returns
        -------
            Number of proxies successfully added.
        """
        pass

    # ------------------------------------------------------------------
    # CRUD operations — used by the service layer for administrative tasks
    # ------------------------------------------------------------------

    @abstractmethod
    def save_pool(self, pool: ProxyPool) -> None:
        """Persist a pool (insert or upsert).

        Args:
        ----
            pool: The ProxyPool object to save.
        """
        pass

    @abstractmethod
    def get_pool(self, pool_id: str) -> ProxyPool:
        """Return a pool by its UUID string.

        Raises
        ------
            PoolNotFoundError: If no pool with that ID exists.
        """
        pass

    @abstractmethod
    def list_pools(self) -> Sequence[ProxyPool]:
        """Return all pools."""
        pass

    @abstractmethod
    def delete_pool(self, pool_id: str) -> None:
        """Delete a pool by its UUID string.

        Raises
        ------
            PoolNotFoundError: If no pool with that ID exists.
        """
        pass

    @abstractmethod
    def save_proxy(self, proxy: Proxy) -> None:
        """Persist a proxy (insert or upsert).

        Args:
        ----
            proxy: The Proxy object to save.

        Raises
        ------
            PoolNotFoundError: If the proxy's pool does not exist.
        """
        pass

    @abstractmethod
    def get_proxy(self, proxy_id: str) -> Proxy:
        """Return a proxy by its UUID string.

        Raises
        ------
            ProxyNotFoundError: If no proxy with that ID exists.
        """
        pass

    @abstractmethod
    def list_proxies(self, pool_id: str) -> Sequence[Proxy]:
        """Return all proxies in a pool.

        Raises
        ------
            PoolNotFoundError: If no pool with that ID exists.
        """
        pass

    @abstractmethod
    def delete_proxy(self, proxy_id: str) -> None:
        """Delete a proxy by its UUID string.

        Raises
        ------
            ProxyNotFoundError: If no proxy with that ID exists.
        """
        pass

    @abstractmethod
    def get_lease(self, lease_id: str) -> Optional[Lease]:
        """Return a lease by its UUID string, or None if not found."""
        pass

    @abstractmethod
    def list_leases(self, consumer_id: Optional[str] = None) -> Sequence[Lease]:
        """Return leases, optionally filtered by consumer UUID string."""
        pass
