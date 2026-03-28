from __future__ import annotations

import asyncio
from typing import Optional, Sequence
from uuid import UUID

from ..models import (
    Consumer,
    HealthCheckResult,
    Lease,
    PoolStatsSnapshot,
    Proxy,
    ProxyFilters,
    ProxyHealthRecord,
    ProxyPool,
    SelectorStrategy,
)
from .async_interface import IAsyncStorage
from .in_memory import InMemoryStorage


class AsyncInMemoryStorage(IAsyncStorage):
    """
    Async adapter wrapping ``InMemoryStorage`` for asyncio-based callers.

    All ``IAsyncStorage`` methods delegate to the underlying synchronous
    ``InMemoryStorage`` via ``asyncio.to_thread``, keeping the event loop
    free. The sync setup helpers (``add_pool``, ``add_proxy``, etc.) are
    exposed directly so test fixtures do not need special handling.

    Notes
    -----
    This adapter shares the same thread-safety guarantees as
    ``InMemoryStorage``: an ``RLock`` guards every mutating operation.
    ``asyncio.to_thread`` runs each call in the default thread-pool
    executor, so concurrent ``await`` calls are safe.
    """

    def __init__(self) -> None:
        """Initialize with a fresh ``InMemoryStorage`` backend."""
        self._backend = InMemoryStorage()

    # ------------------------------------------------------------------
    # Setup helpers (sync — mirrors InMemoryStorage public API)
    # ------------------------------------------------------------------

    def add_pool(self, pool: ProxyPool) -> None:
        """Add a proxy pool (sync, for test fixtures)."""
        self._backend.add_pool(pool)

    def add_consumer(self, consumer: Consumer) -> None:
        """Add a consumer (sync, for test fixtures)."""
        self._backend.add_consumer(consumer)

    def add_proxy(self, proxy: Proxy) -> None:
        """Add a proxy to its pool (sync, for test fixtures)."""
        self._backend.add_proxy(proxy)

    def get_proxy_by_id(self, proxy_id: UUID) -> Optional[Proxy]:
        """Retrieve a proxy by ID (sync, for assertions in tests)."""
        return self._backend.get_proxy_by_id(proxy_id)

    # ------------------------------------------------------------------
    # IAsyncStorage implementation
    # ------------------------------------------------------------------

    async def find_available_proxy(
        self,
        pool_name: str,
        filters: Optional[ProxyFilters] = None,
        selector: Optional[SelectorStrategy] = None,
    ) -> Optional[Proxy]:
        """Find an available proxy from a named pool (non-blocking)."""
        return await asyncio.to_thread(
            self._backend.find_available_proxy, pool_name, filters, selector
        )

    async def create_lease(
        self, proxy: Proxy, consumer_name: str, duration_seconds: int
    ) -> Lease:
        """Create a new lease (non-blocking)."""
        return await asyncio.to_thread(
            self._backend.create_lease, proxy, consumer_name, duration_seconds
        )

    async def ensure_consumer(self, consumer_name: str) -> UUID:
        """Ensure a consumer entry exists and return its ID (non-blocking)."""
        return await asyncio.to_thread(self._backend.ensure_consumer, consumer_name)

    async def release_lease(self, lease: Lease) -> None:
        """Release an existing lease (non-blocking)."""
        await asyncio.to_thread(self._backend.release_lease, lease)

    async def cleanup_expired_leases(self) -> int:
        """Find and release all expired leases (non-blocking)."""
        return await asyncio.to_thread(self._backend.cleanup_expired_leases)

    async def apply_health_check_result(
        self, result: HealthCheckResult
    ) -> Optional[Proxy]:
        """Persist a health check outcome (non-blocking)."""
        return await asyncio.to_thread(
            self._backend.apply_health_check_result, result
        )

    async def get_last_health_result(
        self, proxy_id: UUID
    ) -> Optional[HealthCheckResult]:
        """Return the most recent health check result for a proxy (non-blocking)."""
        return await asyncio.to_thread(self._backend.get_last_health_result, proxy_id)

    async def get_pool_stats(self, pool_name: str) -> Optional[PoolStatsSnapshot]:
        """Return aggregate stats for a pool (non-blocking)."""
        return await asyncio.to_thread(self._backend.get_pool_stats, pool_name)

    async def add_proxies_bulk(self, proxies: Sequence[Proxy]) -> int:
        """Add multiple proxies in a single operation (non-blocking)."""
        return await asyncio.to_thread(self._backend.add_proxies_bulk, proxies)

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    async def save_pool(self, pool: ProxyPool) -> None:
        """Persist a pool (non-blocking)."""
        await asyncio.to_thread(self._backend.save_pool, pool)

    async def get_pool(self, pool_id: str) -> ProxyPool:
        """Return a pool by its UUID string (non-blocking)."""
        return await asyncio.to_thread(self._backend.get_pool, pool_id)

    async def list_pools(self) -> Sequence[ProxyPool]:
        """Return all pools (non-blocking)."""
        return await asyncio.to_thread(self._backend.list_pools)

    async def delete_pool(self, pool_id: str) -> None:
        """Delete a pool by its UUID string (non-blocking)."""
        await asyncio.to_thread(self._backend.delete_pool, pool_id)

    async def save_proxy(self, proxy: Proxy) -> None:
        """Persist a proxy (non-blocking)."""
        await asyncio.to_thread(self._backend.save_proxy, proxy)

    async def get_proxy(self, proxy_id: str) -> Proxy:
        """Return a proxy by its UUID string (non-blocking)."""
        return await asyncio.to_thread(self._backend.get_proxy, proxy_id)

    async def list_proxies(self, pool_id: str) -> Sequence[Proxy]:
        """Return all proxies in a pool (non-blocking)."""
        return await asyncio.to_thread(self._backend.list_proxies, pool_id)

    async def delete_proxy(self, proxy_id: str) -> None:
        """Delete a proxy by its UUID string (non-blocking)."""
        await asyncio.to_thread(self._backend.delete_proxy, proxy_id)

    async def get_lease(self, lease_id: str) -> Optional[Lease]:
        """Return a lease by its UUID string (non-blocking)."""
        return await asyncio.to_thread(self._backend.get_lease, lease_id)

    async def list_leases(self, consumer_id: Optional[str] = None) -> Sequence[Lease]:
        """Return leases, optionally filtered by consumer (non-blocking)."""
        return await asyncio.to_thread(self._backend.list_leases, consumer_id)

    async def save_health_record(self, record: ProxyHealthRecord) -> None:
        """Persist an immutable health check observation (non-blocking)."""
        await asyncio.to_thread(self._backend.save_health_record, record)

    async def list_health_records(
        self, proxy_id: UUID, limit: int = 100
    ) -> Sequence[ProxyHealthRecord]:
        """Return the most recent health check records for a proxy (non-blocking)."""
        return await asyncio.to_thread(
            self._backend.list_health_records, proxy_id, limit
        )
