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


class IAsyncStorage(ABC):
    """
    Async variant of ``IStorage`` for asyncio-based workflows.

    All methods are coroutines, making this interface suitable for use with
    async storage backends (e.g. asyncpg) or wrappers around sync backends
    that delegate to ``asyncio.to_thread``.
    """

    @abstractmethod
    async def find_available_proxy(
        self,
        pool_name: str,
        filters: Optional[ProxyFilters] = None,
        selector: Optional[SelectorStrategy] = None,
    ) -> Optional[Proxy]:
        """
        Find an available proxy from a named pool that meets the criteria.

        Parameters
        ----------
        pool_name:
            The unique name of the pool to search in.
        filters:
            Optional criteria to filter proxies by.
        selector:
            Strategy hint for how to pick between available proxies.

        Returns
        -------
        Optional[Proxy]
            A Proxy object if one is available, otherwise None.
        """

    @abstractmethod
    async def create_lease(
        self, proxy: Proxy, consumer_name: str, duration_seconds: int
    ) -> Lease:
        """
        Create a new lease for a given proxy and consumer.

        Parameters
        ----------
        proxy:
            The proxy to lease.
        consumer_name:
            The name of the entity requesting the lease.
        duration_seconds:
            The duration of the lease in seconds.

        Returns
        -------
        Lease
            The newly created Lease object.
        """

    @abstractmethod
    async def ensure_consumer(self, consumer_name: str) -> UUID:
        """Ensure a consumer entry exists and return its ID."""

    @abstractmethod
    async def release_lease(self, lease: Lease) -> None:
        """
        Release an existing lease.

        Parameters
        ----------
        lease:
            The lease to release.
        """

    @abstractmethod
    async def cleanup_expired_leases(self) -> int:
        """
        Find and release all expired leases.

        Returns
        -------
        int
            The number of leases that were cleaned up.
        """

    @abstractmethod
    async def apply_health_check_result(
        self, result: HealthCheckResult
    ) -> Optional[Proxy]:
        """
        Persist the outcome of a health check for a proxy.

        Parameters
        ----------
        result:
            Result data produced by a health check execution.

        Returns
        -------
        Optional[Proxy]
            A copy of the updated proxy, or None if the proxy was not found.
        """

    @abstractmethod
    async def get_pool_stats(self, pool_name: str) -> Optional[PoolStatsSnapshot]:
        """Return aggregate stats for a pool."""

    @abstractmethod
    async def add_proxies_bulk(self, proxies: Sequence[Proxy]) -> int:
        """
        Add multiple proxies in a single operation.

        Parameters
        ----------
        proxies:
            The proxy objects to add.

        Returns
        -------
        int
            Number of proxies successfully added.
        """

    # ------------------------------------------------------------------
    # CRUD operations — used by the service layer for administrative tasks
    # ------------------------------------------------------------------

    @abstractmethod
    async def save_pool(self, pool: ProxyPool) -> None:
        """Persist a pool (insert or upsert)."""

    @abstractmethod
    async def get_pool(self, pool_id: str) -> ProxyPool:
        """Return a pool by its UUID string.

        Raises
        ------
        PoolNotFoundError
            If no pool with that ID exists.
        """

    @abstractmethod
    async def list_pools(self) -> Sequence[ProxyPool]:
        """Return all pools."""

    @abstractmethod
    async def delete_pool(self, pool_id: str) -> None:
        """Delete a pool by its UUID string.

        Raises
        ------
        PoolNotFoundError
            If no pool with that ID exists.
        """

    @abstractmethod
    async def save_proxy(self, proxy: Proxy) -> None:
        """Persist a proxy (insert or upsert).

        Raises
        ------
        PoolNotFoundError
            If the proxy's pool does not exist.
        """

    @abstractmethod
    async def get_proxy(self, proxy_id: str) -> Proxy:
        """Return a proxy by its UUID string.

        Raises
        ------
        ProxyNotFoundError
            If no proxy with that ID exists.
        """

    @abstractmethod
    async def list_proxies(self, pool_id: str) -> Sequence[Proxy]:
        """Return all proxies in a pool.

        Raises
        ------
        PoolNotFoundError
            If no pool with that ID exists.
        """

    @abstractmethod
    async def delete_proxy(self, proxy_id: str) -> None:
        """Delete a proxy by its UUID string.

        Raises
        ------
        ProxyNotFoundError
            If no proxy with that ID exists.
        """

    @abstractmethod
    async def get_lease(self, lease_id: str) -> Optional[Lease]:
        """Return a lease by its UUID string, or None if not found."""

    @abstractmethod
    async def list_leases(self, consumer_id: Optional[str] = None) -> Sequence[Lease]:
        """Return leases, optionally filtered by consumer UUID string."""
