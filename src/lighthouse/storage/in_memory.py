import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from uuid import UUID

from lighthouse.models import (
    Client,
    Lease,
    LeaseStatus,
    Proxy,
    ProxyFilters,
    ProxyPool,
)
from lighthouse.storage.interface import IStorage


class _InMemoryPool:
    """Represent a single pool of proxies in memory. (Internal class)."""

    def __init__(self, name: str):
        self.name = name
        self.proxies: Dict[UUID, Proxy] = {}

    def add_proxy(self, proxy: Proxy):
        """Add a proxy to the pool's internal dictionary."""
        self.proxies[proxy.id] = proxy

    def get_proxy(self, proxy_id: UUID) -> Optional[Proxy]:
        """Get a proxy from the pool by its ID."""
        return self.proxies.get(proxy_id)

    def find_available_proxy(self, filters: Optional[ProxyFilters]) -> Optional[Proxy]:
        """Find the first available proxy in this pool that matches filters."""
        for proxy in self.proxies.values():
            if proxy.status != "active":
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
        """Check if a proxy matches all provided filters."""
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
    """
    An object-oriented, thread-safe in-memory storage implementation.

    This adapter simulates a database in memory, making it ideal for testing
    and development environments.
    """

    def __init__(self):
        """Initialize the in-memory storage."""
        self._lock = threading.RLock()
        self._pools: Dict[UUID, _InMemoryPool] = {}
        self._proxy_pools: Dict[UUID, ProxyPool] = {}
        self._clients: Dict[UUID, Client] = {}
        self._leases: Dict[UUID, Lease] = {}

        self._pool_name_to_id: Dict[str, UUID] = {}
        self._client_name_to_id: Dict[str, UUID] = {}
        self._proxy_id_to_pool_id: Dict[UUID, UUID] = {}

    def add_pool(self, pool: ProxyPool):
        """Add a proxy pool to the storage for testing.

        Args:
        ----
            pool: The ProxyPool object to add.
        """
        with self._lock:
            pool_copy = pool.model_copy(deep=True)
            self._proxy_pools[pool_copy.id] = pool_copy
            self._pool_name_to_id[pool_copy.name] = pool_copy.id
            self._pools[pool_copy.id] = _InMemoryPool(name=pool_copy.name)

    def add_client(self, client: Client):
        """Add a client to the storage for testing.

        Args:
        ----
            client: The Client object to add.
        """
        with self._lock:
            client_copy = client.model_copy(deep=True)
            self._clients[client_copy.id] = client_copy
            self._client_name_to_id[client_copy.name] = client_copy.id

    def add_proxy(self, proxy: Proxy):
        """Add a proxy to its corresponding pool in the storage.

        Args:
        ----
            proxy: The Proxy object to add.

        Raises
        ------
            ValueError: If the proxy's pool_id does not exist in the storage.
        """
        with self._lock:
            p_copy = proxy.model_copy(deep=True)
            pool_id = p_copy.pool_id
            if pool_id not in self._pools:
                raise ValueError(f"Pool with ID {pool_id} does not exist.")
            self._pools[pool_id].add_proxy(p_copy)
            self._proxy_id_to_pool_id[p_copy.id] = pool_id

    def get_proxy_by_id(self, proxy_id: UUID) -> Optional[Proxy]:
        """Retrieve a proxy directly by its ID.

        Args:
        ----
            proxy_id: The UUID of the proxy to retrieve.

        Returns
        -------
            A copy of the Proxy object if found, otherwise None.
        """
        with self._lock:
            pool_id = self._proxy_id_to_pool_id.get(proxy_id)
            if pool_id:
                if pool := self._pools.get(pool_id):
                    if proxy := pool.get_proxy(proxy_id):
                        return proxy.model_copy(deep=True)
        return None

    def find_available_proxy(
        self, pool_name: str, filters: Optional[ProxyFilters] = None
    ) -> Optional[Proxy]:
        """Find an available proxy from a named pool that meets the criteria."""
        with self._lock:
            pool_id = self._pool_name_to_id.get(pool_name)
            if not pool_id:
                return None

            pool = self._pools.get(pool_id)
            if not pool:
                return None

            proxy_found = pool.find_available_proxy(filters)
            if proxy_found:
                return proxy_found.model_copy(deep=True)
        return None

    def create_lease(
        self, proxy: Proxy, client_name: str, duration_seconds: int
    ) -> Lease:
        """Create a new lease for a given proxy and client name."""
        with self._lock:
            client_id = self._client_name_to_id.get(client_name)
            if not client_id:
                raise ValueError(f"Client with name '{client_name}' not found.")

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

            pool = self._pools[proxy_in_storage.pool_id]
            pool.proxies[proxy_in_storage.id].current_leases += 1

            return lease.model_copy(deep=True)

    def release_lease(self, lease: Lease) -> None:
        """Release an existing lease."""
        with self._lock:
            lease_in_storage = self._leases.get(lease.id)
            if not lease_in_storage or lease_in_storage.status == LeaseStatus.RELEASED:
                return

            lease_in_storage.status = LeaseStatus.RELEASED
            lease_in_storage.released_at = datetime.now(timezone.utc)

            proxy_in_storage = self.get_proxy_by_id(lease.proxy_id)
            if proxy_in_storage:
                pool = self._pools[proxy_in_storage.pool_id]
                pool.proxies[proxy_in_storage.id].current_leases = max(
                    0, pool.proxies[proxy_in_storage.id].current_leases - 1
                )

    def cleanup_expired_leases(self) -> int:
        """Find and release all expired leases."""
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
