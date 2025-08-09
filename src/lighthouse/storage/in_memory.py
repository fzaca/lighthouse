import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from uuid import UUID

from lighthouse.models import (
    Lease,
    LeaseStatus,
    Proxy,
    ProxyFilters,
    ProxyStatus,
)
from lighthouse.storage.interface import IStorage


class _InMemoryPool:
    """Represents a single pool of proxies in memory. (Internal class)."""

    def __init__(self, name: str):
        self.name = name
        self.proxies: Dict[UUID, Proxy] = {}

    def add_proxy(self, proxy: Proxy):
        self.proxies[proxy.id] = proxy

    def get_proxy(self, proxy_id: UUID) -> Optional[Proxy]:
        return self.proxies.get(proxy_id)

    def find_available_proxy(self, filters: Optional[ProxyFilters]) -> Optional[Proxy]:
        """Find the first available proxy in this pool that matches filters."""
        for proxy in self.proxies.values():
            if proxy.status != ProxyStatus.ACTIVE:
                continue

            is_available = (
                proxy.max_concurrency is None
                or proxy.current_leases < proxy.max_concurrency
            )
            if not is_available:
                continue

            if self._proxy_matches_filters(proxy, filters):
                return proxy
        return None

    def _proxy_matches_filters(
        self, proxy: Proxy, filters: Optional[ProxyFilters]
    ) -> bool:
        """Help method to check if a proxy matches all provided filters."""
        if not filters:
            return True
        if filters.source and proxy.source != filters.source:
            return False
        if filters.country and proxy.country != filters.country:
            return False
        if filters.city and proxy.city != filters.city:
            return False
        if filters.isp and proxy.isp != filters.isp:
            return False
        if filters.asn and proxy.asn != filters.asn:
            return False
        return True


class InMemoryStorage(IStorage):
    """An object-oriented, thread-safe in-memory storage implementation."""

    def __init__(self):
        self._lock = threading.RLock()
        self._pools: Dict[str, _InMemoryPool] = {}
        self._leases: Dict[UUID, Lease] = {}
        self._proxy_id_to_pool_name: Dict[UUID, str] = {}

    # --- Helper methods for tests ---

    def add_proxy(self, proxy: Proxy):
        """Help method to add a proxy to the storage for testing."""
        with self._lock:
            p_copy = proxy.model_copy(deep=True)
            pool_name = p_copy.pool_name
            if pool_name not in self._pools:
                self._pools[pool_name] = _InMemoryPool(name=pool_name)
            self._pools[pool_name].add_proxy(p_copy)
            self._proxy_id_to_pool_name[p_copy.id] = pool_name

    def get_proxy_by_id(self, proxy_id: UUID) -> Optional[Proxy]:
        """Help method to retrieve a proxy directly by its ID for testing."""
        with self._lock:
            pool_name = self._proxy_id_to_pool_name.get(proxy_id)
            if pool_name:
                if pool := self._pools.get(pool_name):
                    if proxy := pool.get_proxy(proxy_id):
                        return proxy.model_copy(deep=True)
        return None

    # --- IStorage Implementation ---

    def find_available_proxy(
        self, pool_name: str, filters: Optional[ProxyFilters] = None
    ) -> Optional[Proxy]:
        """Find an available proxy that meets the specified criteria.

        This implementation retrieves the first available proxy from the
        given pool that is active, has available concurrency slots, and
        matches the optional filters provided.

        Args:
            pool_name: The name of the pool to search in.
            filters: Optional criteria to filter proxies by.

        Returns
        -------
            A Proxy object if one is available, otherwise None.
        """
        with self._lock:
            pool = self._pools.get(pool_name)
            if not pool:
                return None

            proxy_found = pool.find_available_proxy(filters)
            if proxy_found:
                return proxy_found.model_copy(deep=True)
        return None

    def create_lease(
        self, proxy: Proxy, client_id: UUID, duration_seconds: int
    ) -> Lease:
        """Create a new lease for a given proxy and client.

        This method generates a new lease record with a calculated expiration
        time and atomically increments the `current_leases` count on the
        proxy object within the storage.

        Args:
            proxy: The proxy to lease.
            client_id: The ID of the client requesting the lease.
            duration_seconds: The duration of the lease in seconds.

        Returns
        -------
            The newly created Lease object.

        Raises
        ------
            ValueError: If the proxy with the given ID is not found in storage.
            RuntimeError: If the proxy is no longer available (e.g., due to a
                race condition).
        """
        with self._lock:
            proxy_in_storage = self.get_proxy_by_id(proxy.id)
            if not proxy_in_storage:
                raise ValueError(f"Proxy with ID {proxy.id} not found in storage.")

            is_available = (
                proxy_in_storage.max_concurrency is None
                or proxy_in_storage.current_leases < proxy_in_storage.max_concurrency
            )
            if not is_available:
                raise RuntimeError(f"Proxy {proxy.id} is no longer available.")

            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(seconds=duration_seconds)

            lease = Lease(
                proxy_id=proxy.id,
                client_id=client_id,
                expires_at=expires_at,
                acquired_at=now,
            )

            self._leases[lease.id] = lease

            pool = self._pools[proxy_in_storage.pool_name]
            pool.proxies[proxy_in_storage.id].current_leases += 1

            return lease.model_copy(deep=True)

    def release_lease(self, lease: Lease) -> None:
        """Release an existing lease and free up a concurrency slot.

        This method marks a lease as released and atomically decrements the
        `current_leases` count on the associated proxy.

        Args:
            lease: The lease to release.
        """
        with self._lock:
            lease_in_storage = self._leases.get(lease.id)
            if not lease_in_storage or lease_in_storage.status == LeaseStatus.RELEASED:
                return

            lease_in_storage.status = LeaseStatus.RELEASED
            lease_in_storage.released_at = datetime.now(timezone.utc)

            proxy_in_storage = self.get_proxy_by_id(lease.proxy_id)
            if proxy_in_storage:
                pool = self._pools[proxy_in_storage.pool_name]
                pool.proxies[proxy_in_storage.id].current_leases = max(
                    0, pool.proxies[proxy_in_storage.id].current_leases - 1
                )

    def cleanup_expired_leases(self) -> int:
        """Find and release all expired leases.

        This method iterates through all active leases, identifies those
        whose `expires_at` timestamp is in the past, and releases them.

        Returns
        -------
            The number of leases that were cleaned up.
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            leases_to_check = list(self._leases.values())
            expired_leases = [
                lease for lease in leases_to_check
                if lease.status == LeaseStatus.ACTIVE and lease.expires_at < now
            ]

            for lease in expired_leases:
                self.release_lease(lease)

            return len(expired_leases)
