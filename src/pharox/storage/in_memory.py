import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from ..models import (
    Consumer,
    HealthCheckResult,
    Lease,
    LeaseStatus,
    PoolStatsSnapshot,
    Proxy,
    ProxyFilters,
    ProxyPool,
    ProxyStatus,
    SelectorStrategy,
)
from .interface import IStorage


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
        available = self.available_proxies(filters)
        return available[0] if available else None

    def available_proxies(self, filters: Optional[ProxyFilters]) -> List[Proxy]:
        """Return all available proxies in this pool for the given filters."""
        results: List[Proxy] = []
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
                results.append(proxy)
        return results

    def _proxy_matches_filters(
        self, proxy: Proxy, filters: Optional[ProxyFilters]
    ) -> bool:
        """Check if a proxy matches all provided filters."""
        if not filters:
            return True
        return filters.matches(proxy)


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
        self._leases: Dict[UUID, Lease] = {}

        self._pool_name_to_id: Dict[str, UUID] = {}
        self._consumer_name_to_id: Dict[str, UUID] = {}
        self._proxy_id_to_pool_id: Dict[UUID, UUID] = {}
        self._round_robin_cursors: Dict[UUID, int] = {}

    def add_pool(self, pool: ProxyPool):
        """Add a proxy pool to the storage for testing.

        Args:
        ----
            pool: The ProxyPool object to add.
        """
        with self._lock:
            pool_copy = pool.model_copy(deep=True)
            self._pool_name_to_id[pool_copy.name] = pool_copy.id
            self._pools[pool_copy.id] = _InMemoryPool(name=pool_copy.name)

    def add_consumer(self, consumer: Consumer):
        """Add a consumer to the storage for testing.

        Args:
        ----
            consumer: The Consumer object to add.
        """
        with self._lock:
            consumer_copy = consumer.model_copy(deep=True)
            self._consumer_name_to_id[consumer_copy.name] = consumer_copy.id

    def ensure_consumer(self, consumer_name: str) -> UUID:
        """Ensure a consumer with the given name exists and return its ID."""
        with self._lock:
            if consumer_name in self._consumer_name_to_id:
                return self._consumer_name_to_id[consumer_name]
            consumer = Consumer(name=consumer_name)
            self._consumer_name_to_id[consumer_name] = consumer.id
            return consumer.id

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
        self,
        pool_name: str,
        filters: Optional[ProxyFilters] = None,
        selector: Optional[SelectorStrategy] = None,
    ) -> Optional[Proxy]:
        """Find an available proxy from a named pool that meets the criteria."""
        with self._lock:
            pool_id = self._pool_name_to_id.get(pool_name)
            if not pool_id:
                return None

            pool = self._pools.get(pool_id)
            if not pool:
                return None

            available = pool.available_proxies(filters)
            if not available:
                return None

            strategy = selector or SelectorStrategy.FIRST_AVAILABLE
            proxy_found = self._apply_selector(pool_id, available, strategy)
            if proxy_found:
                return proxy_found.model_copy(deep=True)
        return None

    def _apply_selector(
        self,
        pool_id: UUID,
        available: List[Proxy],
        strategy: SelectorStrategy,
    ) -> Optional[Proxy]:
        if not available:
            return None
        if strategy == SelectorStrategy.LEAST_USED:
            return min(
                available,
                key=lambda proxy: (
                    proxy.current_leases,
                    proxy.checked_at,
                    proxy.id,
                ),
            )
        if strategy == SelectorStrategy.ROUND_ROBIN:
            return self._select_round_robin(pool_id, available)
        return available[0]

    def _select_round_robin(
        self, pool_id: UUID, available: List[Proxy]
    ) -> Proxy:
        ordered = sorted(available, key=lambda proxy: proxy.id)
        total = len(ordered)
        cursor = self._round_robin_cursors.get(pool_id, 0) % total
        proxy = ordered[cursor]
        self._round_robin_cursors[pool_id] = (cursor + 1) % total
        return proxy

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
        with self._lock:
            consumer_id = self._consumer_name_to_id.get(consumer_name)
            if not consumer_id:
                raise ValueError(f"Consumer with name '{consumer_name}' not found.")

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

            pool = self._pools[proxy_in_storage.pool_id]

            lease = Lease(
                proxy_id=proxy.id,
                consumer_id=consumer_id,
                pool_id=proxy_in_storage.pool_id,
                pool_name=pool.name,
                expires_at=expires_at,
                acquired_at=now,
            )

            self._leases[lease.id] = lease

            pool.proxies[proxy_in_storage.id].current_leases += 1

            return lease.model_copy(deep=True)

    def release_lease(self, lease: Lease) -> None:
        """
        Release an existing lease.

        Args:
        ----
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
                pool = self._pools[proxy_in_storage.pool_id]
                pool.proxies[proxy_in_storage.id].current_leases = max(
                    0, pool.proxies[proxy_in_storage.id].current_leases - 1
                )

    def cleanup_expired_leases(self) -> int:
        """
        Find and release all expired leases.

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

    def apply_health_check_result(
        self, result: HealthCheckResult
    ) -> Optional[Proxy]:
        """
        Update proxy status and checked_at based on a health check result.

        Args:
        ----
            result: Outcome of the health check to persist.

        Returns
        -------
            A copy of the updated Proxy, or None if it could not be located.
        """
        with self._lock:
            pool_id = self._proxy_id_to_pool_id.get(result.proxy_id)
            if pool_id is None:
                return None

            pool = self._pools.get(pool_id)
            if pool is None:
                return None

            proxy = pool.proxies.get(result.proxy_id)
            if proxy is None:
                return None

            proxy.status = result.status
            proxy.checked_at = result.checked_at

            return proxy.model_copy(deep=True)

    def get_pool_stats(self, pool_name: str) -> Optional[PoolStatsSnapshot]:
        """Return aggregate stats for the requested pool."""
        with self._lock:
            pool_id = self._pool_name_to_id.get(pool_name)
            if pool_id is None:
                return None

            pool = self._pools.get(pool_id)
            if pool is None:
                return None

            proxies = list(pool.proxies.values())
            total_proxies = len(proxies)
            active_proxies = sum(
                1 for proxy in proxies if proxy.status == ProxyStatus.ACTIVE
            )
            available_proxies = sum(
                1
                for proxy in proxies
                if proxy.status == ProxyStatus.ACTIVE
                and (
                    proxy.max_concurrency is None
                    or proxy.current_leases < proxy.max_concurrency
                )
            )
            leased_proxies = sum(1 for proxy in proxies if proxy.current_leases > 0)
            total_leases = sum(proxy.current_leases for proxy in proxies)

            return PoolStatsSnapshot(
                pool_name=pool.name,
                total_proxies=total_proxies,
                active_proxies=active_proxies,
                available_proxies=available_proxies,
                leased_proxies=leased_proxies,
                total_leases=total_leases,
            )
